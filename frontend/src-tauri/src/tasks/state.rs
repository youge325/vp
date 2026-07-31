//! Single-task lifecycle state machine.
//!
//! A start lease reserves the only task slot before any child process is
//! created. Every later transition is matched by lease id so a stale cleanup
//! task can never clear a newer task.

use std::sync::atomic::{AtomicU64, Ordering};

use tokio::sync::{mpsc, Mutex};
use tokio::task::JoinHandle;

use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::TaskControlMessage;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum TaskStateError {
    AlreadyRunning,
    StartLeaseExpired,
    NoActiveTask,
    StillStarting,
    AlreadyCancelling,
    AlreadyFinishing,
    Reaping,
    CleanupFailed,
}

#[derive(Debug, Clone)]
pub(super) struct StartLease {
    id: u64,
    cancel_token: CancellationToken,
}

impl PartialEq for StartLease {
    fn eq(&self, other: &Self) -> bool {
        self.id == other.id
    }
}

impl Eq for StartLease {}

impl StartLease {
    pub(super) fn cancellation_token(&self) -> CancellationToken {
        self.cancel_token.clone()
    }
}

struct ActiveTask {
    lease: StartLease,
    control_tx: Option<mpsc::Sender<TaskControlMessage>>,
    terminal_committed: bool,
    cleanup_observer: Option<JoinHandle<()>>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ActivePhase {
    Starting,
    Running,
    Cancelling,
    Finishing,
    Reaping,
    CleanupFailed,
}

#[derive(Default)]
enum TaskStatePhase {
    #[default]
    Idle,
    Active {
        task: ActiveTask,
        phase: ActivePhase,
    },
}

#[derive(Default)]
pub(crate) struct TaskState {
    next_lease_id: AtomicU64,
    phase: Mutex<TaskStatePhase>,
}

impl TaskState {
    /// Reserve the single task slot before performing any side effects.
    pub(super) async fn reserve_start(&self) -> Result<StartLease, TaskStateError> {
        let mut guard = self.phase.lock().await;
        if !matches!(*guard, TaskStatePhase::Idle) {
            return Err(TaskStateError::AlreadyRunning);
        }
        let lease = StartLease {
            id: self.next_lease_id.fetch_add(1, Ordering::Relaxed) + 1,
            cancel_token: CancellationToken::new(),
        };
        *guard = TaskStatePhase::Active {
            task: ActiveTask {
                lease: lease.clone(),
                control_tx: None,
                terminal_committed: false,
                cleanup_observer: None,
            },
            phase: ActivePhase::Starting,
        };
        Ok(lease)
    }

    /// Publish the task handle after the child and its channels are ready.
    pub(super) async fn activate(
        &self,
        lease: &StartLease,
        control_tx: mpsc::Sender<TaskControlMessage>,
    ) -> Result<(), TaskStateError> {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active { task, phase }
                if task.lease == *lease && *phase == ActivePhase::Starting =>
            {
                task.control_tx = Some(control_tx);
                *phase = if task.lease.cancel_token.is_cancelled() {
                    ActivePhase::Cancelling
                } else {
                    ActivePhase::Running
                };
                Ok(())
            }
            _ => Err(TaskStateError::StartLeaseExpired),
        }
    }

    /// Release a failed start without disturbing a different task.
    pub(super) async fn rollback_start(&self, lease: &StartLease) {
        let mut guard = self.phase.lock().await;
        if matches!(
            &*guard,
            TaskStatePhase::Active { task, phase: ActivePhase::Starting }
                if task.lease == *lease
        ) {
            *guard = TaskStatePhase::Idle;
        }
    }

    /// Move a failed startup into cleanup ownership before touching the child.
    pub(super) async fn begin_start_cleanup(&self, lease: &StartLease) -> bool {
        self.transition_owned(lease, &[ActivePhase::Starting], ActivePhase::Reaping)
            .await
    }

    /// Mark a live task as being reaped. Reaping never makes the slot reusable.
    pub(super) async fn begin_reaping(&self, lease: &StartLease) -> bool {
        self.transition_owned(
            lease,
            &[
                ActivePhase::Running,
                ActivePhase::Cancelling,
                ActivePhase::Finishing,
                ActivePhase::Reaping,
            ],
            ActivePhase::Reaping,
        )
        .await
    }

    async fn transition_owned(
        &self,
        lease: &StartLease,
        allowed: &[ActivePhase],
        target: ActivePhase,
    ) -> bool {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active { task, phase }
                if task.lease == *lease && allowed.contains(phase) =>
            {
                *phase = target;
                true
            }
            _ => false,
        }
    }

    /// Keep the slot closed when the stable process owner cannot confirm reap.
    /// The terminal callback is committed at most once for this lease.
    pub(super) async fn fail_cleanup_once(
        &self,
        lease: &StartLease,
        terminal: impl FnOnce(),
    ) -> bool {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active { task, phase }
                if task.lease == *lease
                    && matches!(phase, ActivePhase::Reaping | ActivePhase::CleanupFailed) =>
            {
                *phase = ActivePhase::CleanupFailed;
                if task.terminal_committed {
                    return false;
                }
                task.terminal_committed = true;
                terminal();
                true
            }
            _ => false,
        }
    }

    /// A late reaper may reopen a CleanupFailed slot, but must not emit again.
    pub(super) async fn confirm_cleanup(&self, lease: &StartLease) -> bool {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active {
                task,
                phase: ActivePhase::CleanupFailed,
            } if task.lease == *lease => {
                // The observer calling this method is normally the handle stored here. Taking
                // and dropping that handle detaches only its final, non-awaiting return path;
                // the process/control cleanup has already been confirmed at this point.
                task.cleanup_observer.take();
                *guard = TaskStatePhase::Idle;
                true
            }
            _ => false,
        }
    }

    /// Retain the sole late-cleanup observer in the owning task state.
    ///
    /// A CleanupFailed slot must never depend on a discarded `JoinHandle`: if ownership was
    /// lost or an observer is already installed, the rejected task is explicitly aborted.
    pub(super) async fn own_cleanup_observer(
        &self,
        lease: &StartLease,
        observer: JoinHandle<()>,
    ) -> bool {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active {
                task,
                phase: ActivePhase::CleanupFailed,
            } if task.lease == *lease && task.cleanup_observer.is_none() => {
                task.cleanup_observer = Some(observer);
                true
            }
            _ => {
                observer.abort();
                false
            }
        }
    }

    /// Atomically transition the lifecycle and install the first cancellation reason.
    ///
    /// A start reservation already owns its cancellation token, so an immediate cancel can
    /// be recorded before the child handle is published. `activate` then publishes the task
    /// directly as `Cancelling` and the supervisor observes the same token.
    pub(super) async fn begin_cancel(&self, reason: CancelReason) -> Result<(), TaskStateError> {
        let mut guard = self.phase.lock().await;
        transition_cancel(&mut guard, reason)
    }

    /// Install a supervisor-originated reason only when this lease still owns the task.
    pub(super) async fn cancel_owned(&self, lease: &StartLease, reason: CancelReason) -> bool {
        let mut guard = self.phase.lock().await;
        let TaskStatePhase::Active { task, .. } = &*guard else {
            return false;
        };
        if task.lease != *lease {
            return false;
        }
        transition_cancel(&mut guard, reason).is_ok()
    }

    /// Seal the owning task once process exit or a terminal envelope is observed.
    ///
    /// The transition is atomic with user cancellation: whichever lifecycle action
    /// acquires the state lock first owns the terminal outcome. A sealed task rejects
    /// later pause, resume, and cancel requests while the supervisor drains its pipes.
    pub(super) async fn seal_owned(&self, lease: &StartLease) -> bool {
        let mut guard = self.phase.lock().await;
        match &mut *guard {
            TaskStatePhase::Active { task, phase }
                if task.lease == *lease
                    && matches!(phase, ActivePhase::Running | ActivePhase::Finishing) =>
            {
                *phase = ActivePhase::Finishing;
                true
            }
            _ => false,
        }
    }

    pub(super) async fn control_sender(
        &self,
    ) -> Result<mpsc::Sender<TaskControlMessage>, TaskStateError> {
        let guard = self.phase.lock().await;
        match &*guard {
            TaskStatePhase::Idle => Err(TaskStateError::NoActiveTask),
            TaskStatePhase::Active {
                phase: ActivePhase::Starting,
                task,
            } if task.lease.cancel_token.is_cancelled() => Err(TaskStateError::AlreadyCancelling),
            TaskStatePhase::Active {
                phase: ActivePhase::Starting,
                ..
            } => Err(TaskStateError::StillStarting),
            TaskStatePhase::Active {
                phase: ActivePhase::Running,
                task,
            } => task.control_tx.clone().ok_or(TaskStateError::StillStarting),
            TaskStatePhase::Active { phase, .. } => Err(unavailable_phase_error(*phase)),
        }
    }

    /// Emit/commit a terminal action exactly once, before making the slot reusable.
    ///
    /// The callback runs while the lifecycle mutex still protects the owning lease. Therefore
    /// a newer task cannot reserve the slot until the old terminal event has been queued, and a
    /// stale or duplicate supervisor cannot emit a second terminal event.
    pub(super) async fn finish_once(
        &self,
        lease: &StartLease,
        before_release: impl FnOnce(),
    ) -> bool {
        let mut guard = self.phase.lock().await;
        let owns_phase = matches!(
            &*guard,
            TaskStatePhase::Active { task, phase: ActivePhase::Reaping }
                if task.lease == *lease
        );
        if owns_phase {
            before_release();
            *guard = TaskStatePhase::Idle;
            true
        } else {
            false
        }
    }
}

fn transition_cancel(
    state: &mut TaskStatePhase,
    reason: CancelReason,
) -> Result<(), TaskStateError> {
    match state {
        TaskStatePhase::Idle => Err(TaskStateError::NoActiveTask),
        TaskStatePhase::Active { task, phase }
            if matches!(phase, ActivePhase::Starting | ActivePhase::Running) =>
        {
            if task.lease.cancel_token.cancel(reason) {
                if *phase == ActivePhase::Running {
                    *phase = ActivePhase::Cancelling;
                }
                Ok(())
            } else {
                Err(TaskStateError::AlreadyCancelling)
            }
        }
        TaskStatePhase::Active { phase, .. } => Err(unavailable_phase_error(*phase)),
    }
}

fn unavailable_phase_error(phase: ActivePhase) -> TaskStateError {
    match phase {
        ActivePhase::Starting | ActivePhase::Running | ActivePhase::Cancelling => {
            TaskStateError::AlreadyCancelling
        }
        ActivePhase::Finishing => TaskStateError::AlreadyFinishing,
        ActivePhase::Reaping => TaskStateError::Reaping,
        ActivePhase::CleanupFailed => TaskStateError::CleanupFailed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_control_sender() -> mpsc::Sender<TaskControlMessage> {
        let (tx, _rx) = mpsc::channel(1);
        tx
    }

    async fn start(state: &TaskState) -> StartLease {
        let lease = state.reserve_start().await.expect("reserve");
        state
            .activate(&lease, make_control_sender())
            .await
            .expect("activate");
        lease
    }

    async fn reap_and_finish(state: &TaskState, lease: &StartLease) -> bool {
        state.begin_reaping(lease).await && state.finish_once(lease, || {}).await
    }

    async fn reap_and_finish_with(
        state: &TaskState,
        lease: &StartLease,
        before_release: impl FnOnce(),
    ) -> bool {
        state.begin_reaping(lease).await && state.finish_once(lease, before_release).await
    }

    #[tokio::test]
    async fn idle_state_reports_no_active_task() {
        let state = TaskState::default();

        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::NoActiveTask)
        ));
    }

    #[tokio::test]
    async fn owning_rollback_releases_a_starting_slot() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");

        state.rollback_start(&lease).await;

        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::NoActiveTask)
        ));
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn rollback_after_activation_does_not_clear_running_task() {
        let state = TaskState::default();
        let lease = start(&state).await;

        state.rollback_start(&lease).await;

        assert!(state.control_sender().await.is_ok());
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn finish_once_requires_confirmed_reaping_phase() {
        let state = TaskState::default();
        let lease = start(&state).await;

        assert!(!state.finish_once(&lease, || {}).await);
        assert_eq!(
            state.reserve_start().await,
            Err(TaskStateError::AlreadyRunning)
        );
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn lease_ids_increase_when_a_failed_start_is_retried() {
        let state = TaskState::default();
        let first = state.reserve_start().await.expect("first lease");
        state.rollback_start(&first).await;
        let second = state.reserve_start().await.expect("second lease");

        assert!(second.id > first.id);
    }

    #[tokio::test]
    async fn reservation_blocks_a_concurrent_start_before_spawn() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("first reservation");
        assert_eq!(
            state.reserve_start().await,
            Err(TaskStateError::AlreadyRunning)
        );
        state.rollback_start(&lease).await;
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn only_the_owning_lease_can_activate_or_rollback() {
        let state = TaskState::default();
        let first = state.reserve_start().await.expect("reserve");
        state.rollback_start(&first).await;
        let second = state.reserve_start().await.expect("reserve again");

        assert_eq!(
            state.activate(&first, make_control_sender()).await,
            Err(TaskStateError::StartLeaseExpired)
        );
        state.rollback_start(&first).await;
        state
            .activate(&second, make_control_sender())
            .await
            .expect("current lease remains active");
    }

    #[tokio::test]
    async fn stale_finish_does_not_clear_a_newer_task() {
        let state = TaskState::default();
        let first = start(&state).await;
        assert!(reap_and_finish(&state, &first).await);
        let second = start(&state).await;

        assert!(!reap_and_finish(&state, &first).await);
        assert!(state.control_sender().await.is_ok());
        assert!(reap_and_finish(&state, &second).await);
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::NoActiveTask)
        ));
    }

    #[tokio::test]
    async fn cancel_transition_is_atomic_and_duplicate_cancel_is_rejected() {
        let state = TaskState::default();
        let lease = start(&state).await;
        assert!(state.begin_cancel(CancelReason::User).await.is_ok());
        assert!(matches!(
            state.begin_cancel(CancelReason::User).await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn starting_task_accepts_cancel_without_publishing_a_process_handle() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::StillStarting)
        ));
        assert!(
            state.begin_cancel(CancelReason::User).await.is_ok(),
            "a cancellation racing startup must be recorded on the start lease"
        );
        assert_eq!(
            lease.cancellation_token().reason(),
            Some(CancelReason::User)
        );
        state
            .activate(&lease, make_control_sender())
            .await
            .expect("cancelled reservation can still publish its supervisor handle");
        assert!(matches!(
            state.begin_cancel(CancelReason::User).await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn activation_and_cancel_race_preserves_the_cancellation_reason() {
        for _ in 0..100 {
            let state = TaskState::default();
            let lease = state.reserve_start().await.expect("reserve");
            let barrier = tokio::sync::Barrier::new(2);
            let (activation, cancellation) = tokio::join!(
                async {
                    barrier.wait().await;
                    state.activate(&lease, make_control_sender()).await
                },
                async {
                    barrier.wait().await;
                    state.begin_cancel(CancelReason::User).await
                },
            );

            activation.expect("activation wins before or after cancellation");
            cancellation.expect("cancellation wins before or after activation");
            assert!(matches!(
                state.control_sender().await,
                Err(TaskStateError::AlreadyCancelling)
            ));
            assert_eq!(
                lease.cancellation_token().reason(),
                Some(CancelReason::User)
            );
            assert!(reap_and_finish(&state, &lease).await);
        }
    }

    #[tokio::test]
    async fn cancelled_starting_task_reports_already_cancelling() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        assert!(state.begin_cancel(CancelReason::Stalled).await.is_ok());

        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        state.rollback_start(&lease).await;
    }

    #[tokio::test]
    async fn activating_a_cancelled_lease_preserves_its_reason_on_the_handle() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        assert!(state.begin_cancel(CancelReason::Stalled).await.is_ok());

        state
            .activate(&lease, make_control_sender())
            .await
            .expect("activate cancelling task");
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        assert_eq!(
            lease.cancellation_token().reason(),
            Some(CancelReason::Stalled)
        );
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn begin_cancel_rejects_an_idle_state() {
        let state = TaskState::default();

        assert!(matches!(
            state.begin_cancel(CancelReason::User).await,
            Err(TaskStateError::NoActiveTask)
        ));
    }

    #[tokio::test]
    async fn cancel_owned_rejects_a_lease_after_rollback() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        state.rollback_start(&lease).await;

        assert!(!state.cancel_owned(&lease, CancelReason::Stalled).await);
        assert_eq!(lease.cancellation_token().reason(), None);
    }

    #[tokio::test]
    async fn cancel_owned_can_mark_a_starting_lease_before_activation() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");

        assert!(state.cancel_owned(&lease, CancelReason::Stalled).await);
        assert_eq!(
            lease.cancellation_token().reason(),
            Some(CancelReason::Stalled)
        );
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::AlreadyCancelling)
        ));
        state.rollback_start(&lease).await;
    }

    #[tokio::test]
    async fn finish_once_does_not_finalize_an_unactivated_lease() {
        use std::sync::atomic::{AtomicBool, Ordering};

        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        let callback_ran = AtomicBool::new(false);

        assert!(
            !state
                .finish_once(&lease, || callback_ran.store(true, Ordering::SeqCst))
                .await
        );
        assert!(!callback_ran.load(Ordering::SeqCst));
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::StillStarting)
        ));
        state.rollback_start(&lease).await;
    }

    #[tokio::test]
    async fn cancelling_task_can_be_finished_by_its_owning_lease() {
        let state = TaskState::default();
        let lease = start(&state).await;
        assert!(state.begin_cancel(CancelReason::User).await.is_ok());

        assert!(reap_and_finish(&state, &lease).await);
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::NoActiveTask)
        ));
    }

    #[tokio::test]
    async fn sealed_task_rejects_late_cancellation_and_control_access() {
        let state = TaskState::default();
        let lease = start(&state).await;

        assert!(state.seal_owned(&lease).await);
        assert!(matches!(
            state.begin_cancel(CancelReason::User).await,
            Err(TaskStateError::AlreadyFinishing)
        ));
        assert_eq!(lease.cancellation_token().reason(), None);
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::AlreadyFinishing)
        ));
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn cancellation_that_wins_before_sealing_keeps_its_terminal_reason() {
        let state = TaskState::default();
        let lease = start(&state).await;

        state
            .begin_cancel(CancelReason::User)
            .await
            .expect("cancel first");

        assert!(!state.seal_owned(&lease).await);
        assert_eq!(
            lease.cancellation_token().reason(),
            Some(CancelReason::User)
        );
        assert!(reap_and_finish(&state, &lease).await);
    }

    #[tokio::test]
    async fn terminal_callback_runs_once_and_before_the_slot_is_reused() {
        use std::sync::atomic::{AtomicUsize, Ordering};

        let state = TaskState::default();
        let lease = start(&state).await;
        let calls = AtomicUsize::new(0);

        assert!(
            reap_and_finish_with(&state, &lease, || {
                calls.fetch_add(1, Ordering::SeqCst);
            })
            .await
        );
        assert!(
            !state
                .finish_once(&lease, || {
                    calls.fetch_add(1, Ordering::SeqCst);
                })
                .await
        );
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn supervisor_cancellation_is_lease_bound_and_records_the_reason() {
        let state = TaskState::default();
        let first = start(&state).await;
        assert!(
            state.cancel_owned(&first, CancelReason::Stalled).await,
            "the owning supervisor must transition Running to Cancelling"
        );
        assert_eq!(
            first.cancellation_token().reason(),
            Some(CancelReason::Stalled)
        );
        assert!(
            !state.cancel_owned(&first, CancelReason::User).await,
            "the first cancellation reason wins"
        );
        assert!(reap_and_finish(&state, &first).await);

        let second = start(&state).await;
        assert!(
            !state.cancel_owned(&first, CancelReason::Stalled).await,
            "a stale supervisor must not cancel a newer task"
        );
        assert_eq!(second.cancellation_token().reason(), None);
        assert!(reap_and_finish(&state, &second).await);
    }

    #[tokio::test]
    async fn reaping_keeps_the_single_task_slot_closed_until_reap_is_confirmed() {
        let state = TaskState::default();
        let lease = start(&state).await;

        assert!(state.begin_reaping(&lease).await);
        assert_eq!(
            state.reserve_start().await,
            Err(TaskStateError::AlreadyRunning)
        );
        assert!(matches!(
            state.control_sender().await,
            Err(TaskStateError::Reaping)
        ));
        assert!(state.finish_once(&lease, || {}).await);
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn cleanup_failure_is_sticky_and_commits_terminal_once() {
        use std::sync::atomic::{AtomicUsize, Ordering};

        let state = TaskState::default();
        let lease = start(&state).await;
        let terminals = AtomicUsize::new(0);
        assert!(state.begin_reaping(&lease).await);
        assert!(
            state
                .fail_cleanup_once(&lease, || {
                    terminals.fetch_add(1, Ordering::SeqCst);
                })
                .await
        );
        assert!(
            !state
                .fail_cleanup_once(&lease, || {
                    terminals.fetch_add(1, Ordering::SeqCst);
                })
                .await
        );
        assert_eq!(terminals.load(Ordering::SeqCst), 1);
        assert_eq!(
            state.reserve_start().await,
            Err(TaskStateError::AlreadyRunning)
        );
        assert!(state.confirm_cleanup(&lease).await);
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn cleanup_observer_is_owned_until_late_reap_confirmation() {
        let state = std::sync::Arc::new(TaskState::default());
        let lease = start(state.as_ref()).await;
        assert!(state.begin_reaping(&lease).await);
        assert!(state.fail_cleanup_once(&lease, || {}).await);

        let (release, released) = tokio::sync::oneshot::channel();
        let observer_state = std::sync::Arc::clone(&state);
        let observer_lease = lease.clone();
        let observer = tokio::spawn(async move {
            released.await.expect("release cleanup observer");
            assert!(observer_state.confirm_cleanup(&observer_lease).await);
        });

        assert!(state.own_cleanup_observer(&lease, observer).await);
        assert_eq!(
            state.reserve_start().await,
            Err(TaskStateError::AlreadyRunning)
        );
        release.send(()).expect("release observer");

        tokio::time::timeout(std::time::Duration::from_secs(1), async {
            loop {
                if let Ok(next) = state.reserve_start().await {
                    state.rollback_start(&next).await;
                    break;
                }
                tokio::task::yield_now().await;
            }
        })
        .await
        .expect("owned observer must release CleanupFailed after confirmation");
    }
}
