use std::env;
use std::io;
use std::process::ExitStatus;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use command_group::AsyncGroupChild;
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::{mpsc, oneshot};

use crate::models::TaskErrorPayload;
use crate::process_control::{self, ProcessController};
use crate::protocol::TaskEventName;
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::runner::ProgressBeat;
use crate::tasks::state::{TaskControlKind, TaskControlMessage, TaskState};
use crate::tasks::stderr::StderrCapture;

const DEFAULT_STALL_TIMEOUT_SECS: u64 = 600;
const WATCHDOG_POLL_INTERVAL_SECS: u64 = 5;
const STALL_TIMEOUT_ENV: &str = "VP_TASK_STALL_TIMEOUT_SECS";

#[allow(clippy::too_many_arguments)]
pub fn spawn_task_controller<R: Runtime + 'static>(
    app: AppHandle<R>,
    child: AsyncGroupChild,
    root_pid: u32,
    mut control_rx: mpsc::Receiver<TaskControlMessage>,
    terminal_sent: Arc<AtomicBool>,
    stderr_capture: StderrCapture,
    cancel_token: CancellationToken,
    progress_beat: ProgressBeat,
) {
    let controller: Arc<dyn ProcessController> = process_control::default_controller();

    // Oneshot kill signal to the wait task — single-use, never dropped silently.
    let (kill_tx, kill_rx) = oneshot::channel::<()>();
    // Oneshot for the wait task to report the child exit status.
    let (exit_tx, mut exit_rx) = oneshot::channel::<io::Result<ExitStatus>>();

    // Wait task: owns AsyncGroupChild, waits for natural exit or kill.
    tauri::async_runtime::spawn(async move {
        let mut child = child;
        tokio::select! {
            _ = kill_rx => {
                let _ = child.kill().await;
                let status = child.wait().await;
                let _ = exit_tx.send(status);
            }
            status = child.wait() => {
                let _ = exit_tx.send(status);
            }
        }
    });

    // Optional stall watchdog: polls ``progress_beat`` and cancels the
    // token with ``Stalled`` reason if no stdout progress arrives within
    // the configured window. Disabled by ``VP_TASK_STALL_TIMEOUT_SECS=0``.
    if let Some(timeout) = parse_stall_timeout() {
        let watchdog_token = cancel_token.clone();
        let watchdog_beat = progress_beat.clone();
        tauri::async_runtime::spawn(async move {
            let mut interval =
                tokio::time::interval(Duration::from_secs(WATCHDOG_POLL_INTERVAL_SECS));
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
            loop {
                interval.tick().await;
                if watchdog_token.is_cancelled() {
                    break;
                }
                let elapsed = watchdog_beat.lock().ok().map(|guard| guard.elapsed());
                if let Some(elapsed) = elapsed {
                    if elapsed > timeout {
                        watchdog_token.cancel(CancelReason::Stalled);
                        break;
                    }
                }
            }
        });
    }

    // Controller task: handles Pause / Resume, dispatches cancel, waits for exit.
    tauri::async_runtime::spawn(async move {
        let mut is_paused = false;
        let mut control_rx_closed = false;
        let mut kill_dispatched = false;
        let mut kill_tx = Some(kill_tx);
        let status: io::Result<ExitStatus>;

        loop {
            tokio::select! {
                maybe_message = control_rx.recv(), if !control_rx_closed => {
                    let Some(message) = maybe_message else {
                        control_rx_closed = true;
                        continue;
                    };
                    let result = handle_pause_resume(
                        &*controller,
                        root_pid,
                        &cancel_token,
                        message.kind,
                        &mut is_paused,
                    );
                    let _ = message.response.send(result);
                }
                _ = cancel_token.cancelled(), if !kill_dispatched => {
                    kill_dispatched = true;
                    if is_paused {
                        let _ = controller.resume(root_pid);
                        is_paused = false;
                    }
                    if let Some(tx) = kill_tx.take() {
                        let _ = tx.send(());
                    }
                }
                wait_result = &mut exit_rx => {
                    status = match wait_result {
                        Ok(status) => status,
                        Err(_) => Err(io::Error::new(
                            io::ErrorKind::Other,
                            "wait task was dropped",
                        )),
                    };
                    break;
                }
            }
        }

        {
            let state = app.state::<TaskState>();
            let mut guard = state.current.lock().await;
            *guard = None;
        }

        emit_terminal_event(
            &app,
            status,
            terminal_sent.load(Ordering::SeqCst),
            &cancel_token,
            &stderr_capture,
        );
    });
}

fn emit_terminal_event<R: Runtime>(
    app: &AppHandle<R>,
    status: io::Result<ExitStatus>,
    terminal_sent: bool,
    cancel_token: &CancellationToken,
    stderr_capture: &StderrCapture,
) {
    if let Some(reason) = cancel_token.reason() {
        match reason {
            CancelReason::User => {
                let _ = app.emit(TaskEventName::TaskCancelled.as_str(), ());
                return;
            }
            CancelReason::Stalled => {
                let details = stderr_capture
                    .summary()
                    .map(|traceback| json!({ "traceback": traceback, "stalled": true }));
                let _ = app.emit(
                    TaskEventName::TaskError.as_str(),
                    TaskErrorPayload {
                        code: crate::protocol::TaskErrorCode::ProcessFailed,
                        message: "Backend stalled — no progress within the configured timeout.".to_string(),
                        details,
                    },
                );
                return;
            }
        }
    }

    match status {
        Ok(exit_status) => {
            if !exit_status.success() && !terminal_sent {
                let details = stderr_capture
                    .summary()
                    .map(|traceback| json!({ "traceback": traceback }));
                let _ = app.emit(
                    TaskEventName::TaskError.as_str(),
                    TaskErrorPayload {
                        code: crate::protocol::TaskErrorCode::RuntimePanic,
                        message: format!("Backend process exited with status {}.", exit_status),
                        details,
                    },
                );
            }
        }
        Err(error) => {
            if !terminal_sent {
                let details = stderr_capture
                    .summary()
                    .map(|traceback| json!({ "traceback": traceback }));
                let _ = app.emit(
                    TaskEventName::TaskError.as_str(),
                    TaskErrorPayload {
                        code: crate::protocol::TaskErrorCode::ProcessFailed,
                        message: format!("Failed while waiting for backend process: {error}"),
                        details,
                    },
                );
            }
        }
    }
}

fn handle_pause_resume(
    controller: &dyn ProcessController,
    root_pid: u32,
    cancel_token: &CancellationToken,
    kind: TaskControlKind,
    is_paused: &mut bool,
) -> Result<(), String> {
    if cancel_token.is_cancelled() {
        return Err("The task is already being cancelled.".to_string());
    }
    match kind {
        TaskControlKind::Pause => {
            if *is_paused {
                return Ok(());
            }
            controller.suspend(root_pid)?;
            *is_paused = true;
            Ok(())
        }
        TaskControlKind::Resume => {
            if !*is_paused {
                return Ok(());
            }
            controller.resume(root_pid)?;
            *is_paused = false;
            Ok(())
        }
    }
}

fn parse_stall_timeout() -> Option<Duration> {
    let raw = env::var(STALL_TIMEOUT_ENV).ok();
    let secs = match raw {
        Some(value) => match value.trim().parse::<u64>() {
            Ok(parsed) => parsed,
            Err(_) => DEFAULT_STALL_TIMEOUT_SECS,
        },
        None => DEFAULT_STALL_TIMEOUT_SECS,
    };
    if secs == 0 {
        None
    } else {
        Some(Duration::from_secs(secs))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn parse_stall_timeout_uses_default_when_unset() {
        // Use an env var that almost certainly is not set.
        let stash = env::var(STALL_TIMEOUT_ENV).ok();
        env::remove_var(STALL_TIMEOUT_ENV);
        let timeout = parse_stall_timeout();
        assert_eq!(timeout, Some(Duration::from_secs(DEFAULT_STALL_TIMEOUT_SECS)));
        if let Some(value) = stash {
            env::set_var(STALL_TIMEOUT_ENV, value);
        }
    }

    #[test]
    fn parse_stall_timeout_returns_none_for_zero() {
        let stash = env::var(STALL_TIMEOUT_ENV).ok();
        env::set_var(STALL_TIMEOUT_ENV, "0");
        assert_eq!(parse_stall_timeout(), None);
        if let Some(value) = stash {
            env::set_var(STALL_TIMEOUT_ENV, value);
        } else {
            env::remove_var(STALL_TIMEOUT_ENV);
        }
    }

    #[test]
    fn parse_stall_timeout_falls_back_to_default_on_malformed_input() {
        let stash = env::var(STALL_TIMEOUT_ENV).ok();
        env::set_var(STALL_TIMEOUT_ENV, "not-a-number");
        assert_eq!(
            parse_stall_timeout(),
            Some(Duration::from_secs(DEFAULT_STALL_TIMEOUT_SECS))
        );
        if let Some(value) = stash {
            env::set_var(STALL_TIMEOUT_ENV, value);
        } else {
            env::remove_var(STALL_TIMEOUT_ENV);
        }
    }

    #[test]
    fn handle_pause_resume_rejects_when_cancelled() {
        struct NoopController;
        impl ProcessController for NoopController {
            fn suspend(&self, _pid: u32) -> Result<(), String> {
                Ok(())
            }
            fn resume(&self, _pid: u32) -> Result<(), String> {
                Ok(())
            }
        }
        let token = CancellationToken::new();
        token.cancel(CancelReason::User);
        let mut paused = false;
        let result = handle_pause_resume(
            &NoopController,
            1234,
            &token,
            TaskControlKind::Pause,
            &mut paused,
        );
        assert!(result.is_err());
        assert!(!paused);
    }

    #[test]
    fn handle_pause_resume_is_idempotent() {
        struct NoopController;
        impl ProcessController for NoopController {
            fn suspend(&self, _pid: u32) -> Result<(), String> {
                Ok(())
            }
            fn resume(&self, _pid: u32) -> Result<(), String> {
                Ok(())
            }
        }
        let token = CancellationToken::new();
        let mut paused = false;
        assert!(handle_pause_resume(
            &NoopController,
            1,
            &token,
            TaskControlKind::Pause,
            &mut paused,
        )
        .is_ok());
        assert!(paused);
        // Second pause is a no-op, still Ok.
        assert!(handle_pause_resume(
            &NoopController,
            1,
            &token,
            TaskControlKind::Pause,
            &mut paused,
        )
        .is_ok());
        assert!(paused);
    }

    // Quick sanity that the Instant type wires up — used by the watchdog.
    #[test]
    fn instant_elapsed_is_monotonic() {
        let now = Instant::now();
        assert!(now.elapsed() < Duration::from_secs(60));
    }
}
