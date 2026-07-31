//! Pause / resume / cancel commands against a running task.
//!
//! Cancel goes through [`TaskState::begin_cancel`] (Running →
//! Cancelling) so a second cancel call is rejected at the state-machine
//! layer instead of relying on cancellation-token idempotency alone.

use tokio::sync::oneshot;
use tokio::time::{timeout, Duration};

use crate::tasks::cancellation::CancelReason;
use crate::tasks::{
    ProcessControlKind, TaskApplicationError, TaskControlKind, TaskControlMessage, TaskState,
};

const CONTROL_TIMEOUT: Duration = Duration::from_secs(5);

async fn cancel_running_task(state: &TaskState) -> Result<(), TaskApplicationError> {
    // The lifecycle transition and first cancellation reason are installed
    // under one state lock, including when cancellation races startup.
    state.begin_cancel(CancelReason::User).await?;
    Ok(())
}

pub(crate) async fn send_task_control(
    state: &TaskState,
    kind: TaskControlKind,
) -> Result<(), TaskApplicationError> {
    let process_kind = match kind {
        TaskControlKind::Cancel => return cancel_running_task(state).await,
        TaskControlKind::Pause => ProcessControlKind::Pause,
        TaskControlKind::Resume => ProcessControlKind::Resume,
    };
    let control_tx = state.control_sender().await?;

    let (response_tx, response_rx) = oneshot::channel();
    timeout(
        CONTROL_TIMEOUT,
        control_tx.send(TaskControlMessage {
            kind: process_kind,
            response: response_tx,
        }),
    )
    .await
    .map_err(|_| crate::error::ShellError::ControllerUnavailable)?
    .map_err(|_| crate::error::ShellError::ControllerUnavailable)?;

    match timeout(CONTROL_TIMEOUT, response_rx).await {
        Err(_) => Err(crate::error::ShellError::ControllerUnavailable.into()),
        Ok(Ok(result)) => result
            .map_err(crate::error::ShellError::ProcessControl)
            .map_err(Into::into),
        Ok(Err(_)) => Err(crate::error::ShellError::ControllerUnavailable.into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tasks::cancellation::CancellationToken;
    use std::sync::Arc;
    use tokio::sync::mpsc;

    async fn start(state: &TaskState) -> CancellationToken {
        let (tx, _rx) = mpsc::channel(1);
        let lease = state.reserve_start().await.expect("reserve");
        let token = lease.cancellation_token();
        state.activate(&lease, tx).await.expect("activate");
        token
    }

    #[tokio::test]
    async fn cancel_running_task_rejects_when_idle() {
        let state = TaskState::default();
        let result = cancel_running_task(&state).await;
        assert!(matches!(
            result,
            Err(TaskApplicationError::State(
                crate::tasks::TaskStateError::NoActiveTask
            ))
        ));
    }

    #[tokio::test]
    async fn unified_cancel_control_fires_token_and_transitions_state() {
        // The cancel path is fire-and-forget: it flips the
        // cancellation token (which the controller observes via
        // ``cancel_token.cancelled()``) and atomically moves the state
        // machine into ``Cancelling``. A second cancel call must fail
        // because ``begin_cancel`` rejects the duplicate transition.
        let state = TaskState::default();
        let token = start(&state).await;

        send_task_control(&state, TaskControlKind::Cancel)
            .await
            .expect("first cancel ok");
        assert!(token.is_cancelled(), "cancel must fire the token");

        let second = send_task_control(&state, TaskControlKind::Cancel).await;
        assert!(
            matches!(
                second,
                Err(TaskApplicationError::State(
                    crate::tasks::TaskStateError::AlreadyCancelling
                ))
            ),
            "duplicate cancel must be rejected, got: {second:?}",
        );
    }

    #[tokio::test]
    async fn pause_running_task_rejects_when_idle() {
        let state = TaskState::default();
        let result = send_task_control(&state, TaskControlKind::Pause).await;
        assert!(matches!(
            result,
            Err(TaskApplicationError::State(
                crate::tasks::TaskStateError::NoActiveTask
            ))
        ));
    }

    async fn start_with_receiver(
        state: &TaskState,
    ) -> mpsc::Receiver<crate::tasks::TaskControlMessage> {
        let (tx, rx) = mpsc::channel(1);
        let lease = state.reserve_start().await.expect("reserve");
        state.activate(&lease, tx).await.expect("activate");
        rx
    }

    async fn dispatch_control(
        kind: TaskControlKind,
    ) -> (
        tokio::task::JoinHandle<Result<(), TaskApplicationError>>,
        crate::tasks::TaskControlMessage,
    ) {
        let state = Arc::new(TaskState::default());
        let mut rx = start_with_receiver(&state).await;
        let request = tokio::spawn(async move { send_task_control(&state, kind).await });
        let message = rx.recv().await.expect("control request");
        (request, message)
    }

    #[tokio::test]
    async fn pause_is_forwarded_and_waits_for_a_successful_reply() {
        let (request, message) = dispatch_control(TaskControlKind::Pause).await;
        assert_eq!(message.kind, ProcessControlKind::Pause);
        message.response.send(Ok(())).expect("reply");
        request.await.expect("request task").expect("pause result");
    }

    #[tokio::test]
    async fn resume_is_forwarded_with_the_distinct_process_control_kind() {
        let (request, message) = dispatch_control(TaskControlKind::Resume).await;
        assert_eq!(message.kind, ProcessControlKind::Resume);
        message.response.send(Ok(())).expect("reply");
        request.await.expect("request task").expect("resume result");
    }

    #[tokio::test]
    async fn dropped_control_reply_maps_to_controller_unavailable() {
        let (request, message) = dispatch_control(TaskControlKind::Pause).await;
        drop(message.response);
        let result = request.await.expect("request task");
        assert!(matches!(
            result,
            Err(TaskApplicationError::Shell(
                crate::error::ShellError::ControllerUnavailable
            ))
        ));
    }

    #[tokio::test]
    async fn process_control_reply_preserves_the_typed_os_failure() {
        let (request, message) = dispatch_control(TaskControlKind::Pause).await;
        message
            .response
            .send(Err(crate::process_control::ProcessControlError::NotFound))
            .expect("reply");
        let result = request.await.expect("request task");
        assert!(matches!(
            result,
            Err(TaskApplicationError::Shell(
                crate::error::ShellError::ProcessControl(
                    crate::process_control::ProcessControlError::NotFound
                )
            ))
        ));
    }

    #[tokio::test]
    async fn pause_and_resume_unsupported_replies_keep_the_typed_wire_code() {
        for kind in [TaskControlKind::Pause, TaskControlKind::Resume] {
            let (request, message) = dispatch_control(kind).await;
            message
                .response
                .send(Err(
                    crate::process_control::ProcessControlError::Unsupported,
                ))
                .expect("reply");

            let error = request
                .await
                .expect("request task")
                .expect_err("unsupported control must fail");
            let TaskApplicationError::Shell(shell_error) = error else {
                panic!("unsupported control must remain a typed shell error");
            };
            let wire = serde_json::to_value(shell_error).expect("serializable shell error");
            assert_eq!(wire["code"], "process_control_unsupported");
        }
    }

    #[tokio::test]
    async fn closed_control_channel_maps_to_controller_unavailable() {
        let state = TaskState::default();
        let rx = start_with_receiver(&state).await;
        drop(rx);

        let result = send_task_control(&state, TaskControlKind::Pause).await;
        assert!(matches!(
            result,
            Err(TaskApplicationError::Shell(
                crate::error::ShellError::ControllerUnavailable
            ))
        ));
    }

    #[tokio::test]
    async fn pause_while_starting_reports_the_domain_state() {
        let state = TaskState::default();
        let lease = state.reserve_start().await.expect("reserve");

        let result = send_task_control(&state, TaskControlKind::Pause).await;
        assert!(matches!(
            result,
            Err(TaskApplicationError::State(
                crate::tasks::TaskStateError::StillStarting
            ))
        ));
        state.rollback_start(&lease).await;
    }
}
