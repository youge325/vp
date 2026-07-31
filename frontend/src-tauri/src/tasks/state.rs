//! Single-task lifecycle state machine.
//!
//! A start lease reserves the only task slot before any child process is
//! created. Every later transition is matched by lease id so a stale cleanup
//! task can never clear a newer task.

use std::sync::atomic::{AtomicU64, Ordering};

use tokio::sync::{mpsc, Mutex};

use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::handle::TaskHandle;
use crate::tasks::TaskControlMessage;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum TaskStateError {
    AlreadyRunning,
    StartLeaseExpired,
    NoActiveTask,
    StillStarting,
    AlreadyCancelling,
    AlreadyFinishing,
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

#[derive(Default)]
enum TaskStatePhase {
    #[default]
    Idle,
    Starting {
        lease: StartLease,
    },
    Running {
        lease: StartLease,
        handle: TaskHandle,
    },
    Cancelling {
        lease: StartLease,
        handle: TaskHandle,
    },
    Finishing {
        lease: StartLease,
        handle: TaskHandle,
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
        *guard = TaskStatePhase::Starting {
            lease: lease.clone(),
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
        match &*guard {
            TaskStatePhase::Starting {
                lease: current_lease,
            } if current_lease == lease => {
                let handle = TaskHandle::new(control_tx, lease.cancellation_token());
                *guard = if lease.cancel_token.is_cancelled() {
                    TaskStatePhase::Cancelling {
                        lease: lease.clone(),
                        handle,
                    }
                } else {
                    TaskStatePhase::Running {
                        lease: lease.clone(),
                        handle,
                    }
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
            TaskStatePhase::Starting {
                lease: current_lease
            } if current_lease == lease
        ) {
            *guard = TaskStatePhase::Idle;
        }
    }

    /// Atomically transition the lifecycle and install the first cancellation reason.
    ///
    /// A start reservation already owns its cancellation token, so an immediate cancel can
    /// be recorded before the child handle is published. `activate` then publishes the task
    /// directly as `Cancelling` and the supervisor observes the same token.
    pub(super) async fn begin_cancel(&self, reason: CancelReason) -> Result<(), TaskStateError> {
        let mut guard = self.phase.lock().await;
        let current = std::mem::replace(&mut *guard, TaskStatePhase::Idle);
        let (next, result) = transition_cancel(current, reason);
        *guard = next;
        result
    }

    /// Install a supervisor-originated reason only when this lease still owns the task.
    pub(super) async fn cancel_owned(&self, lease: &StartLease, reason: CancelReason) -> bool {
        let mut guard = self.phase.lock().await;
        let owns_phase = match &*guard {
            TaskStatePhase::Starting {
                lease: current_lease,
            }
            | TaskStatePhase::Running {
                lease: current_lease,
                ..
            }
            | TaskStatePhase::Cancelling {
                lease: current_lease,
                ..
            }
            | TaskStatePhase::Finishing {
                lease: current_lease,
                ..
            } => current_lease == lease,
            TaskStatePhase::Idle => false,
        };
        if !owns_phase {
            return false;
        }

        let current = std::mem::replace(&mut *guard, TaskStatePhase::Idle);
        let (next, result) = transition_cancel(current, reason);
        *guard = next;
        result.is_ok()
    }

    /// Seal the owning task once process exit or a terminal envelope is observed.
    ///
    /// The transition is atomic with user cancellation: whichever lifecycle action
    /// acquires the state lock first owns the terminal outcome. A sealed task rejects
    /// later pause, resume, and cancel requests while the supervisor drains its pipes.
    pub(super) async fn seal_owned(&self, lease: &StartLease) -> bool {
        let mut guard = self.phase.lock().await;
        let current = std::mem::replace(&mut *guard, TaskStatePhase::Idle);
        let (next, sealed) = match current {
            TaskStatePhase::Running {
                lease: current_lease,
                handle,
            } if &current_lease == lease => (
                TaskStatePhase::Finishing {
                    lease: current_lease,
                    handle,
                },
                true,
            ),
            TaskStatePhase::Finishing {
                lease: current_lease,
                handle,
            } => {
                let sealed = &current_lease == lease;
                (
                    TaskStatePhase::Finishing {
                        lease: current_lease,
                        handle,
                    },
                    sealed,
                )
            }
            other => (other, false),
        };
        *guard = next;
        sealed
    }

    pub(super) async fn current_handle(&self) -> Result<TaskHandle, TaskStateError> {
        let guard = self.phase.lock().await;
        match &*guard {
            TaskStatePhase::Idle => Err(TaskStateError::NoActiveTask),
            TaskStatePhase::Starting { lease } if lease.cancel_token.is_cancelled() => {
                Err(TaskStateError::AlreadyCancelling)
            }
            TaskStatePhase::Starting { .. } => Err(TaskStateError::StillStarting),
            TaskStatePhase::Running { handle, .. } | TaskStatePhase::Cancelling { handle, .. } => {
                Ok(handle.clone())
            }
            TaskStatePhase::Finishing { .. } => Err(TaskStateError::AlreadyFinishing),
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
        let owns_phase = match &*guard {
            TaskStatePhase::Running {
                lease: current_lease,
                ..
            }
            | TaskStatePhase::Cancelling {
                lease: current_lease,
                ..
            }
            | TaskStatePhase::Finishing {
                lease: current_lease,
                ..
            } => current_lease == lease,
            TaskStatePhase::Idle | TaskStatePhase::Starting { .. } => false,
        };
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
    current: TaskStatePhase,
    reason: CancelReason,
) -> (TaskStatePhase, Result<(), TaskStateError>) {
    match current {
        TaskStatePhase::Idle => (TaskStatePhase::Idle, Err(TaskStateError::NoActiveTask)),
        TaskStatePhase::Starting { lease } => {
            let first = lease.cancel_token.cancel(reason);
            let result = if first {
                Ok(())
            } else {
                Err(TaskStateError::AlreadyCancelling)
            };
            (TaskStatePhase::Starting { lease }, result)
        }
        TaskStatePhase::Running { lease, handle } => {
            let first = handle.cancel_token.cancel(reason);
            let result = if first {
                Ok(())
            } else {
                Err(TaskStateError::AlreadyCancelling)
            };
            (TaskStatePhase::Cancelling { lease, handle }, result)
        }
        TaskStatePhase::Cancelling { lease, handle } => (
            TaskStatePhase::Cancelling { lease, handle },
            Err(TaskStateError::AlreadyCancelling),
        ),
        TaskStatePhase::Finishing { lease, handle } => (
            TaskStatePhase::Finishing { lease, handle },
            Err(TaskStateError::AlreadyFinishing),
        ),
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

    #[tokio::test]
    async fn idle_state_reports_no_active_task() {
        let state = TaskState::default();

        assert!(matches!(
            state.current_handle().await,
            Err(TaskStateError::NoActiveTask)
        ));
    }

    #[tokio::test]
    async fn owning_rollback_releases_a_starting_slot() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");

        state.rollback_start(&lease).await;

        assert!(matches!(
            state.current_handle().await,
            Err(TaskStateError::NoActiveTask)
        ));
        assert!(state.reserve_start().await.is_ok());
    }

    #[tokio::test]
    async fn rollback_after_activation_does_not_clear_running_task() {
        let state = TaskState::default();
        let lease = start(&state).await;

        state.rollback_start(&lease).await;

        assert!(state.current_handle().await.is_ok());
        assert!(state.finish_once(&lease, || {}).await);
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
        assert!(state.finish_once(&first, || {}).await);
        let second = start(&state).await;

        assert!(!state.finish_once(&first, || {}).await);
        assert!(state.current_handle().await.is_ok());
        assert!(state.finish_once(&second, || {}).await);
        assert!(matches!(
            state.current_handle().await,
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
        assert!(state.current_handle().await.is_ok());
        assert!(state.finish_once(&lease, || {}).await);
    }

    #[tokio::test]
    async fn starting_task_accepts_cancel_without_publishing_a_process_handle() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        assert!(matches!(
            state.current_handle().await,
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
        assert!(state.finish_once(&lease, || {}).await);
    }

    #[tokio::test]
    async fn activation_and_cancel_race_preserves_the_cancellation_reason() {
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
        let handle = state
            .current_handle()
            .await
            .expect("published cancelling handle");
        assert_eq!(handle.cancel_token.reason(), Some(CancelReason::User));
        assert!(state.finish_once(&lease, || {}).await);
    }

    #[tokio::test]
    async fn cancelled_starting_task_reports_already_cancelling() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");
        assert!(state.begin_cancel(CancelReason::Stalled).await.is_ok());

        assert!(matches!(
            state.current_handle().await,
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
        let handle = state.current_handle().await.expect("published handle");
        assert_eq!(handle.cancel_token.reason(), Some(CancelReason::Stalled));
        assert!(state.finish_once(&lease, || {}).await);
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
            state.current_handle().await,
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
            state.current_handle().await,
            Err(TaskStateError::StillStarting)
        ));
        state.rollback_start(&lease).await;
    }

    #[tokio::test]
    async fn cancelling_task_can_be_finished_by_its_owning_lease() {
        let state = TaskState::default();
        let lease = start(&state).await;
        assert!(state.begin_cancel(CancelReason::User).await.is_ok());

        assert!(state.finish_once(&lease, || {}).await);
        assert!(matches!(
            state.current_handle().await,
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
            state.current_handle().await,
            Err(TaskStateError::AlreadyFinishing)
        ));
        assert!(state.finish_once(&lease, || {}).await);
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
        assert!(state.finish_once(&lease, || {}).await);
    }

    #[tokio::test]
    async fn terminal_callback_runs_once_and_before_the_slot_is_reused() {
        use std::sync::atomic::{AtomicUsize, Ordering};

        let state = TaskState::default();
        let lease = start(&state).await;
        let calls = AtomicUsize::new(0);

        assert!(
            state
                .finish_once(&lease, || {
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
        assert!(state.finish_once(&first, || {}).await);

        let second = start(&state).await;
        assert!(
            !state.cancel_owned(&first, CancelReason::Stalled).await,
            "a stale supervisor must not cancel a newer task"
        );
        assert_eq!(second.cancellation_token().reason(), None);
        assert!(state.finish_once(&second, || {}).await);
    }
}
