//! Pause / resume / cancel commands against a running task.
//!
//! Split out of the legacy ``tasks::runner`` mod in Phase 5b so each
//! file owns a single responsibility:
//!   - ``oneshot.rs`` runs short-lived CLI subcommands (check / info / inspect-output)
//!   - ``spawn.rs`` launches the long-running ``process`` subcommand
//!   - ``readers.rs`` drains stdout/stderr into Tauri events
//!   - ``control.rs`` (this file) issues control signals to the running task
//!
//! Phase 5d wired these into the new [`TaskState`] state machine:
//! ``cancel_running_task`` goes through ``begin_cancel`` (Running →
//! Cancelling) so a second cancel call is rejected at the state-machine
//! layer instead of relying on cancellation-token idempotency alone.

use tokio::sync::oneshot;

use crate::error::ShellError;
use crate::tasks::cancellation::CancelReason;
use crate::tasks::{TaskControlKind, TaskControlMessage, TaskState};

pub async fn cancel_running_task(state: &TaskState) -> Result<(), ShellError> {
    // Phase 5d — atomic Running → Cancelling. ``begin_cancel`` rejects
    // duplicate calls (Cancelling → Cancelling) and bare-Idle cancels
    // (no task) on its own, replacing the bespoke checks the old code
    // performed against ``Mutex<Option<TaskHandle>>``.
    let handle = state.begin_cancel().await?;
    // Cancellation is fire-and-forget. The controller will react via its
    // ``cancel_token.cancelled()`` branch, resume the child if it was
    // paused, kill it, and emit ``task-cancelled`` once the process exits.
    handle.cancel(CancelReason::User);
    Ok(())
}

pub async fn send_task_control(state: &TaskState, kind: TaskControlKind) -> Result<(), ShellError> {
    // Phase 5d — ``current_handle`` returns the active handle even in
    // the ``Cancelling`` phase so an in-flight pause/resume from the
    // UI lands cleanly during the cancel window; the early reject for
    // "already cancelling" lives below.
    let handle = state.current_handle().await?;

    if handle.cancel_token.is_cancelled() {
        return Err(ShellError::InvalidInput(
            "The task is already being cancelled.".to_string(),
        ));
    }

    let (response_tx, response_rx) = oneshot::channel();
    handle
        .control_tx
        .send(TaskControlMessage {
            kind,
            response: response_tx,
        })
        .await
        .map_err(|_| ShellError::ControllerUnavailable)?;

    // Phase 5a — the controller now replies with a typed
    // [`ProcessControlError`](crate::process_control::ProcessControlError).
    // Phase A —  ``ProcessControlError`` 通过专用 ``ShellError::ProcessControl``
    // 变体向上抛,语义自描述,前端按 ``ProcessFailed`` code 路由。
    // 通道/超时失败仍走 ``ControllerUnavailable``,两条路径在前端表现一致。
    match response_rx.await {
        Ok(result) => result.map_err(ShellError::ProcessControl),
        Err(_) => Err(ShellError::ControllerUnavailable),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tasks::cancellation::{CancelReason, CancellationToken};
    use crate::tasks::handle::TaskHandle;
    use tokio::sync::mpsc;

    fn make_handle() -> TaskHandle {
        let (tx, _rx) = mpsc::channel(1);
        TaskHandle::new(tx, CancellationToken::new())
    }

    #[tokio::test]
    async fn cancel_running_task_rejects_when_idle() {
        let state = TaskState::default();
        let result = cancel_running_task(&state).await;
        assert!(matches!(result, Err(ShellError::NoActiveTask)));
    }

    #[tokio::test]
    async fn cancel_running_task_fires_token_and_transitions_state() {
        // The cancel path is fire-and-forget: it flips the
        // cancellation token (which the controller observes via
        // ``cancel_token.cancelled()``) and atomically moves the state
        // machine into ``Cancelling``. A second cancel call must fail
        // because ``begin_cancel`` rejects the duplicate transition.
        let state = TaskState::default();
        let handle = make_handle();
        let token = handle.cancel_token.clone();
        state.try_start(handle).await.expect("start ok");

        cancel_running_task(&state).await.expect("first cancel ok");
        assert!(token.is_cancelled(), "cancel must fire the token");

        let second = cancel_running_task(&state).await;
        assert!(
            matches!(second, Err(ShellError::InvalidInput(_))),
            "duplicate cancel must be rejected, got: {second:?}",
        );
    }

    #[tokio::test]
    async fn pause_running_task_rejects_when_idle() {
        let state = TaskState::default();
        let result = send_task_control(&state, TaskControlKind::Pause).await;
        assert!(matches!(result, Err(ShellError::NoActiveTask)));
    }

    #[tokio::test]
    async fn pause_running_task_rejects_when_token_already_cancelled() {
        // The state machine is still ``Running`` but the cancellation
        // token has been fired (a previous ``cancel_running_task``
        // call's effect outside this test). Pause / resume should be
        // refused so the UI surfaces a clear "already being cancelled"
        // message instead of silently no-oping.
        let state = TaskState::default();
        let handle = make_handle();
        handle.cancel(CancelReason::User);
        state.try_start(handle).await.expect("start ok");

        let result = send_task_control(&state, TaskControlKind::Pause).await;
        assert!(
            matches!(result, Err(ShellError::InvalidInput(_))),
            "cancelled token must block pause, got: {result:?}",
        );
    }

    #[tokio::test]
    async fn resume_running_task_also_rejects_when_token_already_cancelled() {
        let state = TaskState::default();
        let handle = make_handle();
        handle.cancel(CancelReason::User);
        state.try_start(handle).await.expect("start ok");

        let result = send_task_control(&state, TaskControlKind::Resume).await;
        assert!(matches!(result, Err(ShellError::InvalidInput(_))));
    }
}
