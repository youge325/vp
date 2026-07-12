//! Three-phase task state machine.
//!
//! Phase 5d — replaced the previous ``Mutex<Option<TaskHandle>>`` shim
//! with an explicit ``Idle / Running / Cancelling`` enum guarded by a
//! single ``Mutex<TaskStatePhase>``. The atomic transitions
//! ([`TaskState::try_start`], [`TaskState::begin_cancel`],
//! [`TaskState::finish`]) close the read-then-write race window that
//! used to exist between ``spawn_task``'s "is anything running?" peek
//! and the subsequent write of the new ``TaskHandle``.
//!
//! State diagram:
//!
//! ```text
//!                       try_start(handle)
//!         ┌────────────────────────────────────────┐
//!         │                                        │
//!         ▼            begin_cancel ─→             │
//!      ┌──────┐                              ┌─────────────┐
//!      │ Idle │                              │ Cancelling  │
//!      └──────┘                              └─────────────┘
//!         ▲              finish                    │
//!         └────────────────────────────────────────┘
//!                                                  ▲
//!                                                  │ finish
//!                                                  │
//!                                              ┌─────────┐
//!                                              │ Running │
//!                                              └─────────┘
//!                                                  ▲
//!                                                  │ try_start
//!                                                  │
//!                                                  Idle
//! ```

use std::time::Instant;

use tokio::sync::Mutex;

use crate::error::ShellError;
use crate::tasks::handle::TaskHandle;

/// Lifecycle phase of the single in-flight task.
#[derive(Default)]
enum TaskStatePhase {
    /// No task is running. ``try_start`` is the only legal transition.
    #[default]
    Idle,
    /// A task is running normally. ``begin_cancel`` or ``finish`` are
    /// the legal transitions.
    Running { handle: TaskHandle },
    /// A cancel request has been accepted and propagated to the
    /// controller; we're waiting for the child to actually exit.
    /// ``started_at`` is observability-only — the watchdog may use it
    /// to escalate (e.g. SIGKILL) if the child ignores SIGTERM for
    /// too long. ``finish`` is the only legal transition.
    Cancelling {
        handle: TaskHandle,
        started_at: Instant,
    },
}

#[derive(Default)]
pub(crate) struct TaskState {
    phase: Mutex<TaskStatePhase>,
}

impl TaskState {
    /// Atomically transition `Idle` → `Running { handle }`.
    ///
    /// Returns ``Err(ShellError::InvalidInput)`` when another task is
    /// already running (or being cancelled). The check + write are
    /// performed under the same mutex guard so two concurrent callers
    /// can't both observe `Idle` and both insert a handle.
    ///
    /// Phase 17 — ``is_idle`` fast-peek removed. Previously
    /// ``spawn_task`` did ``if !state.is_idle().await { return Err(...) }``
    /// then handed control to ``try_start``; the peek saved a fork+exec
    /// in the happy path but duplicated the "already running" message
    /// across two files (drift hazard), and the docstring on
    /// ``is_idle`` itself admitted the authoritative check was here.
    /// ``try_start`` is now the only entry point.
    pub(crate) async fn try_start(&self, handle: TaskHandle) -> Result<(), ShellError> {
        let mut guard = self.phase.lock().await;
        if !matches!(*guard, TaskStatePhase::Idle) {
            return Err(ShellError::InvalidInput(
                "A task is already running.".to_string(),
            ));
        }
        *guard = TaskStatePhase::Running { handle };
        Ok(())
    }

    /// Atomically transition `Running` → `Cancelling` and hand back
    /// the active handle so the caller can fire its cancel token.
    ///
    /// Errors:
    /// - ``Idle`` → ``NoActiveTask``
    /// - ``Cancelling`` → ``InvalidInput`` ("already being cancelled")
    pub(crate) async fn begin_cancel(&self) -> Result<TaskHandle, ShellError> {
        let mut guard = self.phase.lock().await;
        // Take the current phase out so we can transition without
        // cloning ``TaskHandle`` twice; restore the original variant
        // on every error path.
        let current = std::mem::replace(&mut *guard, TaskStatePhase::Idle);
        match current {
            TaskStatePhase::Idle => Err(ShellError::NoActiveTask),
            TaskStatePhase::Running { handle } => {
                let cloned = handle.clone();
                *guard = TaskStatePhase::Cancelling {
                    handle,
                    started_at: Instant::now(),
                };
                Ok(cloned)
            }
            TaskStatePhase::Cancelling { handle, started_at } => {
                *guard = TaskStatePhase::Cancelling { handle, started_at };
                Err(ShellError::InvalidInput(
                    "The task is already being cancelled.".to_string(),
                ))
            }
        }
    }

    /// Read-only handle peek for pause / resume forwarding.
    ///
    /// Returns the active handle even in `Cancelling` so an in-flight
    /// pause/resume request that landed during the cancel window
    /// still gets a fair chance at reaching the controller (the
    /// controller's ``cancel_token.cancelled()`` select branch will
    /// race it to the kill path either way; this matches the
    /// pre-Phase-5d semantics).
    pub(crate) async fn current_handle(&self) -> Result<TaskHandle, ShellError> {
        let guard = self.phase.lock().await;
        match &*guard {
            TaskStatePhase::Idle => Err(ShellError::NoActiveTask),
            TaskStatePhase::Running { handle } => Ok(handle.clone()),
            TaskStatePhase::Cancelling { handle, .. } => Ok(handle.clone()),
        }
    }

    /// Drop to `Idle` from any phase. Called by the controller after
    /// the child process exits — clean exit, error, or post-cancel kill
    /// all funnel through here so the next ``try_start`` can succeed.
    pub(crate) async fn finish(&self) {
        let mut guard = self.phase.lock().await;
        *guard = TaskStatePhase::Idle;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tasks::cancellation::CancellationToken;
    use tokio::sync::mpsc;

    fn make_handle() -> TaskHandle {
        let (tx, _rx) = mpsc::channel(1);
        TaskHandle::new(tx, CancellationToken::new())
    }

    // Phase 17 — ``is_idle`` 删除后,"phase 是 Idle"由组合断言间接证明:
    // current_handle() 返回 NoActiveTask + begin_cancel() 返回
    // NoActiveTask + try_start(...) 成功。这三条本来就是 Idle phase 的
    // 完整可观察特征。

    #[tokio::test]
    async fn fresh_state_rejects_handle_reads_and_cancel() {
        let state = TaskState::default();
        assert!(state.current_handle().await.is_err());
        assert!(state.begin_cancel().await.is_err());
    }

    #[tokio::test]
    async fn try_start_transitions_idle_to_running() {
        let state = TaskState::default();
        state
            .try_start(make_handle())
            .await
            .expect("idle accepts start");
        assert!(state.current_handle().await.is_ok());
    }

    #[tokio::test]
    async fn try_start_rejects_when_already_running() {
        let state = TaskState::default();
        state.try_start(make_handle()).await.unwrap();
        let second = state.try_start(make_handle()).await;
        assert!(second.is_err(), "double-start must be rejected");
    }

    #[tokio::test]
    async fn begin_cancel_moves_running_to_cancelling() {
        let state = TaskState::default();
        state.try_start(make_handle()).await.unwrap();
        let _handle = state.begin_cancel().await.expect("running accepts cancel");
        // Cancel a second time should fail with "already being cancelled".
        let again = state.begin_cancel().await;
        assert!(again.is_err());
    }

    #[tokio::test]
    async fn current_handle_is_readable_in_cancelling_phase() {
        let state = TaskState::default();
        state.try_start(make_handle()).await.unwrap();
        let _first = state.begin_cancel().await.unwrap();
        // Pause/resume during the cancel window must still find a handle.
        assert!(state.current_handle().await.is_ok());
    }

    #[tokio::test]
    async fn finish_returns_to_idle_from_running() {
        let state = TaskState::default();
        state.try_start(make_handle()).await.unwrap();
        state.finish().await;
        // Idle phase = a fresh start is accepted.
        state.try_start(make_handle()).await.unwrap();
    }

    #[tokio::test]
    async fn finish_returns_to_idle_from_cancelling() {
        let state = TaskState::default();
        state.try_start(make_handle()).await.unwrap();
        state.begin_cancel().await.unwrap();
        state.finish().await;
        // Idle phase = a fresh start is accepted (would fail with
        // InvalidInput if phase were still Cancelling).
        state.try_start(make_handle()).await.unwrap();
    }

    #[tokio::test]
    async fn finish_on_idle_is_noop() {
        let state = TaskState::default();
        state.finish().await;
        // Idle stays Idle: another start succeeds.
        state.try_start(make_handle()).await.unwrap();
    }
}
