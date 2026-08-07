//! Terminal-event arbitration for a supervised backend process.

use std::io;
use std::process::ExitStatus;

use crate::models::{
    TaskCancelledPayload, TaskCancelledReason, TaskCompletedPayload, TaskErrorCode,
    TaskErrorPayload,
};
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::ports::{TaskDomainEvent, TaskEventSink};
use crate::tasks::stderr::StderrCapture;

enum TerminalEvent {
    Completed(TaskCompletedPayload),
    BackendError(TaskErrorPayload),
    SupervisorError(TaskErrorPayload),
}

#[derive(Default)]
pub(super) struct TerminalState {
    event: Option<TerminalEvent>,
}

impl TerminalState {
    pub(super) fn has_event(&self) -> bool {
        self.event.is_some()
    }

    pub(super) fn record_completed(&mut self, payload: TaskCompletedPayload) -> bool {
        if self.event.is_none() {
            self.event = Some(TerminalEvent::Completed(payload));
            false
        } else {
            self.record_supervisor_error(duplicate_terminal_payload("completed"));
            true
        }
    }

    pub(super) fn record_backend_error(&mut self, payload: TaskErrorPayload) -> bool {
        if self.event.is_none() {
            self.event = Some(TerminalEvent::BackendError(payload));
            false
        } else {
            self.record_supervisor_error(duplicate_terminal_payload("error"));
            true
        }
    }

    pub(super) fn record_supervisor_error(&mut self, payload: TaskErrorPayload) {
        if !matches!(self.event, Some(TerminalEvent::SupervisorError(_))) {
            self.event = Some(TerminalEvent::SupervisorError(payload));
        }
    }

    fn take(self) -> Option<TerminalEvent> {
        self.event
    }
}

fn duplicate_terminal_payload(kind: &str) -> TaskErrorPayload {
    TaskErrorPayload {
        code: TaskErrorCode::SchemaMismatch,
        message: format!(
            "Backend emitted more than one terminal NDJSON envelope; duplicate `{kind}`."
        ),
        details: None,
    }
}

pub(super) fn backend_error_payload(
    code: TaskErrorCode,
    message: String,
    stderr_capture: &StderrCapture,
) -> TaskErrorPayload {
    let details = stderr_capture.summary().map(|traceback| {
        serde_json::Map::from_iter([(
            "traceback".to_string(),
            serde_json::Value::String(traceback),
        )])
    });
    TaskErrorPayload {
        code,
        message,
        details,
    }
}

enum ExitDisposition {
    Success,
    Failed(String),
    WaitFailed(String),
}

fn classify_exit(status: io::Result<ExitStatus>) -> ExitDisposition {
    match status {
        Ok(status) if status.success() => ExitDisposition::Success,
        Ok(status) => ExitDisposition::Failed(status.to_string()),
        Err(error) => ExitDisposition::WaitFailed(error.to_string()),
    }
}

fn resolve_non_cancelled_terminal(
    terminal: Option<TerminalEvent>,
    exit: ExitDisposition,
    stderr_capture: &StderrCapture,
) -> TerminalEvent {
    match terminal {
        Some(TerminalEvent::SupervisorError(payload)) => TerminalEvent::SupervisorError(payload),
        Some(TerminalEvent::BackendError(payload)) => TerminalEvent::BackendError(payload),
        Some(TerminalEvent::Completed(payload)) if matches!(exit, ExitDisposition::Success) => {
            TerminalEvent::Completed(payload)
        }
        Some(TerminalEvent::Completed(_)) | None => {
            let payload = match exit {
                ExitDisposition::Success => backend_error_payload(
                    TaskErrorCode::SchemaMismatch,
                    "Backend exited successfully without a terminal NDJSON envelope.".to_string(),
                    stderr_capture,
                ),
                ExitDisposition::Failed(status) => backend_error_payload(
                    TaskErrorCode::RuntimePanic,
                    format!("Backend process exited with status {status}."),
                    stderr_capture,
                ),
                ExitDisposition::WaitFailed(error) => backend_error_payload(
                    TaskErrorCode::ProcessFailed,
                    format!("Failed while waiting for backend process: {error}"),
                    stderr_capture,
                ),
            };
            TerminalEvent::SupervisorError(payload)
        }
    }
}

pub(super) fn emit_terminal_event(
    event_sink: &dyn TaskEventSink,
    status: io::Result<ExitStatus>,
    terminal: TerminalState,
    cancel_token: &CancellationToken,
    stderr_capture: &StderrCapture,
) -> Result<(), String> {
    if let Some(reason) = cancel_token.reason() {
        let (reason, details) = match reason {
            CancelReason::User => (TaskCancelledReason::User, None),
            CancelReason::Stalled => (
                TaskCancelledReason::Stalled,
                stderr_capture.summary().map(|traceback| {
                    serde_json::Map::from_iter([
                        (
                            "traceback".to_string(),
                            serde_json::Value::String(traceback),
                        ),
                        (
                            "message".to_string(),
                            serde_json::Value::String(
                                "Backend stalled — no progress within the configured timeout."
                                    .to_string(),
                            ),
                        ),
                    ])
                }),
            ),
        };
        return event_sink.emit(TaskDomainEvent::Cancelled(TaskCancelledPayload {
            reason,
            details,
        }));
    }

    match resolve_non_cancelled_terminal(terminal.take(), classify_exit(status), stderr_capture) {
        TerminalEvent::Completed(payload) => event_sink.emit(TaskDomainEvent::Completed(payload)),
        TerminalEvent::BackendError(payload) | TerminalEvent::SupervisorError(payload) => {
            event_sink.emit(TaskDomainEvent::Error(payload))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn completed_payload() -> TaskCompletedPayload {
        TaskCompletedPayload {
            output_path: "D:/out.mp4".to_string(),
            processed_frames: 10,
            time_seconds: 1.0,
        }
    }

    fn task_error(code: TaskErrorCode, message: &str) -> TaskErrorPayload {
        TaskErrorPayload {
            code,
            message: message.to_string(),
            details: None,
        }
    }

    #[test]
    fn duplicate_terminal_becomes_a_schema_failure() {
        let mut terminal = TerminalState::default();
        assert!(!terminal.record_completed(completed_payload()));
        assert!(terminal.record_completed(completed_payload()));

        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
            }
            _ => panic!("duplicate terminal must override completion"),
        }
    }

    #[test]
    fn exit_disposition_table_preserves_only_valid_completion() {
        let cases = [
            (ExitDisposition::Success, TaskErrorCode::SchemaMismatch),
            (
                ExitDisposition::Failed("exit code: 9".to_string()),
                TaskErrorCode::RuntimePanic,
            ),
            (
                ExitDisposition::WaitFailed("wait closed".to_string()),
                TaskErrorCode::ProcessFailed,
            ),
        ];
        for (exit, expected) in cases {
            match resolve_non_cancelled_terminal(None, exit, &StderrCapture::new()) {
                TerminalEvent::SupervisorError(payload) => {
                    assert_eq!(payload.code, expected);
                }
                _ => panic!("missing terminal must fail"),
            }
        }

        match resolve_non_cancelled_terminal(
            Some(TerminalEvent::Completed(completed_payload())),
            ExitDisposition::Success,
            &StderrCapture::new(),
        ) {
            TerminalEvent::Completed(payload) => assert_eq!(payload.processed_frames, 10),
            _ => panic!("valid completion must be preserved"),
        }
    }

    #[test]
    fn backend_error_and_first_supervisor_failure_remain_authoritative() {
        let backend = task_error(TaskErrorCode::MissingModel, "weights unavailable");
        match resolve_non_cancelled_terminal(
            Some(TerminalEvent::BackendError(backend)),
            ExitDisposition::Failed("exit code: 2".to_string()),
            &StderrCapture::new(),
        ) {
            TerminalEvent::BackendError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::MissingModel));
            }
            _ => panic!("typed backend error must retain precedence"),
        }

        let mut terminal = TerminalState::default();
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::SchemaMismatch,
            "first protocol failure",
        ));
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::ProcessFailed,
            "later pipe failure",
        ));
        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert_eq!(payload.message, "first protocol failure");
            }
            _ => panic!("first supervisor failure must remain authoritative"),
        }
    }
}
