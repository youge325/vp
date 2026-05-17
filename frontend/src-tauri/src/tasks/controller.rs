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

use crate::models::{TaskCancelledPayload, TaskCancelledReason, TaskErrorPayload};
use crate::process_control::{ProcessController, ProcessControlError};
use crate::protocol::TaskEventName;
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::readers::ProgressBeat;
use crate::tasks::state::{TaskControlKind, TaskControlMessage, TaskState};
use crate::tasks::stderr::StderrCapture;

const DEFAULT_STALL_TIMEOUT_SECS: u64 = 600;
const DEFAULT_WATCHDOG_POLL_INTERVAL_SECS: u64 = 5;
const STALL_TIMEOUT_ENV: &str = "VP_TASK_STALL_TIMEOUT_SECS";

/// Watchdog configuration for the task controller.
///
/// Phase D.3.2 — previously the poll interval was a hard-coded ``const``
/// and the stall timeout was read from ``VP_TASK_STALL_TIMEOUT_SECS``
/// directly inside ``spawn_task_controller``. Splitting them into a
/// dedicated struct (a) makes the watchdog testable with millisecond
/// timeouts instead of seconds and (b) lets future PRs source the
/// config from app settings without touching the controller spawn site.
#[derive(Debug, Clone, Copy)]
pub struct WatchdogConfig {
    pub poll_interval: Duration,
    /// ``None`` disables the watchdog entirely (matches the legacy
    /// ``VP_TASK_STALL_TIMEOUT_SECS=0`` opt-out).
    pub stall_timeout: Option<Duration>,
}

impl WatchdogConfig {
    pub fn from_env() -> Self {
        Self {
            poll_interval: Duration::from_secs(DEFAULT_WATCHDOG_POLL_INTERVAL_SECS),
            stall_timeout: parse_stall_timeout(),
        }
    }
}

impl Default for WatchdogConfig {
    fn default() -> Self {
        Self::from_env()
    }
}

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
    controller: Arc<dyn ProcessController>,
    watchdog: WatchdogConfig,
) {
    let controller: Arc<dyn ProcessController> = controller;

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
    // the configured window. Disabled by ``watchdog.stall_timeout == None``.
    if let Some(timeout) = watchdog.stall_timeout {
        let watchdog_token = cancel_token.clone();
        let watchdog_beat = progress_beat.clone();
        let poll_interval = watchdog.poll_interval;
        tauri::async_runtime::spawn(async move {
            let mut interval = tokio::time::interval(poll_interval);
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
                        Err(_) => Err(io::Error::other("wait task was dropped")),
                    };
                    break;
                }
            }
        }

        // Phase 5d — drop the state machine back to ``Idle`` through
        // the dedicated transition rather than poking
        // ``state.current`` directly. ``finish`` accepts any phase, so
        // this works for normal completion, error exit, and the
        // cancel-triggered kill path alike.
        {
            let state = app.state::<TaskState>();
            state.finish().await;
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
                let _ = app.emit(
                    TaskEventName::TaskCancelled.as_str(),
                    TaskCancelledPayload {
                        reason: TaskCancelledReason::User,
                        details: None,
                    },
                );
                return;
            }
            CancelReason::Stalled => {
                // Phase D.1.2 — stall is now a cancellation (with reason)
                // rather than a synthetic ``task-error{ProcessFailed}``.
                // The traceback (if any) rides along in ``details`` so the
                // UI can still surface it in the cancel banner.
                let details = stderr_capture.summary().map(|traceback| {
                    json!({
                        "traceback": traceback,
                        "message": "Backend stalled — no progress within the configured timeout.",
                    })
                });
                let _ = app.emit(
                    TaskEventName::TaskCancelled.as_str(),
                    TaskCancelledPayload {
                        reason: TaskCancelledReason::Stalled,
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
                        message: format!("Backend process exited with status {exit_status}."),
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
    kind: TaskControlKind,
    is_paused: &mut bool,
) -> Result<(), ProcessControlError> {
    // Phase 5a — cancellation check moved up to ``send_task_control``
    // (and the controller's ``cancel_token.cancelled()`` select branch
    // races us to the kill path either way). Keeping the check here as
    // well would force the function to carry an unrelated ``CancellationToken``
    // argument and produce a stringly-typed error variant just for
    // this one early-return path. The race window between the outer
    // check and this call is harmless: a suspend/resume against an
    // already-killed process simply surfaces as
    // ``ProcessControlError::NotFound``.
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
    fn handle_pause_resume_is_idempotent() {
        struct NoopController;
        impl ProcessController for NoopController {
            fn suspend(&self, _pid: u32) -> Result<(), ProcessControlError> {
                Ok(())
            }
            fn resume(&self, _pid: u32) -> Result<(), ProcessControlError> {
                Ok(())
            }
        }
        let mut paused = false;
        assert!(handle_pause_resume(
            &NoopController,
            1,
            TaskControlKind::Pause,
            &mut paused,
        )
        .is_ok());
        assert!(paused);
        // Second pause is a no-op, still Ok.
        assert!(handle_pause_resume(
            &NoopController,
            1,
            TaskControlKind::Pause,
            &mut paused,
        )
        .is_ok());
        assert!(paused);
    }

    #[test]
    fn handle_pause_resume_forwards_controller_failure() {
        // Phase 5a — replaces the old "rejects when cancelled" test.
        // The cancellation early-return moved up to ``send_task_control``
        // (see the inline comment in ``handle_pause_resume``). What we
        // still want to lock in here is that a controller failure is
        // surfaced as a typed [`ProcessControlError`] instead of being
        // silently swallowed.
        struct FailingController;
        impl ProcessController for FailingController {
            fn suspend(&self, _pid: u32) -> Result<(), ProcessControlError> {
                Err(ProcessControlError::NotFound)
            }
            fn resume(&self, _pid: u32) -> Result<(), ProcessControlError> {
                Ok(())
            }
        }
        let mut paused = false;
        let result = handle_pause_resume(
            &FailingController,
            1234,
            TaskControlKind::Pause,
            &mut paused,
        );
        assert!(matches!(result, Err(ProcessControlError::NotFound)));
        assert!(!paused, "paused flag must not flip when controller errored");
    }

    // Quick sanity that the Instant type wires up — used by the watchdog.
    #[test]
    fn instant_elapsed_is_monotonic() {
        let now = Instant::now();
        assert!(now.elapsed() < Duration::from_secs(60));
    }
}
