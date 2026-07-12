//! NDJSON stdout / stderr line readers for the running backend task.
//!
//! Split out of the legacy ``tasks::runner`` mod in Phase 5b.
//!
//! Both readers are spawned by [`super::spawn::spawn_task`] right after
//! the child process is launched. They run for the lifetime of the
//! child and emit Tauri events as lines arrive.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde_json::Value;
use tauri::{AppHandle, Emitter, Runtime};
use tokio::io::{AsyncBufReadExt, BufReader};

use crate::models::{TaskErrorCode, TaskErrorPayload, TaskLogPayload};
use crate::protocol::TaskEventName;
use crate::tasks::envelope::NdjsonEnvelope;
use crate::tasks::stderr::StderrCapture;

/// Shared timestamp of the last stdout progress line, refreshed by the
/// stdout reader and polled by the stall watchdog inside the controller.
pub(crate) type ProgressBeat = Arc<Mutex<Instant>>;

pub(crate) fn spawn_stdout_reader<R: Runtime + 'static>(
    app: AppHandle<R>,
    stdout: tokio::process::ChildStdout,
    terminal_sent: Arc<AtomicBool>,
    progress_beat: ProgressBeat,
) {
    tauri::async_runtime::spawn(async move {
        let mut lines = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            match serde_json::from_str::<NdjsonEnvelope>(trimmed) {
                Ok(envelope) => match envelope {
                    NdjsonEnvelope::Progress(payload) => {
                        if let Ok(mut guard) = progress_beat.lock() {
                            *guard = Instant::now();
                        }
                        let _ = app.emit(TaskEventName::TaskProgress.as_str(), payload);
                    }
                    NdjsonEnvelope::Completed(payload) => {
                        terminal_sent.store(true, Ordering::SeqCst);
                        let _ = app.emit(TaskEventName::TaskCompleted.as_str(), payload);
                    }
                    NdjsonEnvelope::ResumeStatus(payload) => {
                        let _ = app.emit(TaskEventName::TaskResumeStatus.as_str(), payload);
                    }
                    NdjsonEnvelope::Error(payload) => {
                        terminal_sent.store(true, Ordering::SeqCst);
                        let _ = app.emit(TaskEventName::TaskError.as_str(), payload);
                    }
                },
                Err(envelope_err) => {
                    // Phase D.1.3 — distinguish two failure modes:
                    //   1. The line is a JSON object that does not match the
                    //      known IPC envelope schema (likely a Rust ↔ Python
                    //      schema drift) → emit ``task-error{SchemaMismatch}``
                    //      so the task aborts loudly rather than silently
                    //      continuing.
                    //   2. The line is plain text (free-form logger output,
                    //      tracebacks, ``[VP_PROGRESS]`` terminal bars) →
                    //      emit ``task-log`` as before.
                    match serde_json::from_str::<Value>(trimmed) {
                        Ok(value) if value.is_object() => {
                            terminal_sent.store(true, Ordering::SeqCst);
                            let type_field = value.get("type").cloned().unwrap_or(Value::Null);
                            let _ = app.emit(
                                TaskEventName::TaskError.as_str(),
                                TaskErrorPayload {
                                    code: TaskErrorCode::SchemaMismatch,
                                    message: format!(
                                        "Backend emitted an NDJSON object that does not match the IPC schema: {envelope_err}"
                                    ),
                                    details: Some(serde_json::json!({
                                        "rawLine": trimmed,
                                        "type": type_field,
                                    })),
                                },
                            );
                        }
                        _ => {
                            let _ = app.emit(
                                TaskEventName::TaskLog.as_str(),
                                TaskLogPayload {
                                    message: trimmed.to_string(),
                                },
                            );
                        }
                    }
                }
            }
        }
    });
}

pub(crate) fn spawn_stderr_reader<R: Runtime + 'static>(
    app: AppHandle<R>,
    stderr: tokio::process::ChildStderr,
    capture: StderrCapture,
) {
    tauri::async_runtime::spawn(async move {
        let mut lines = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            capture.record(trimmed);

            let _ = app.emit(
                TaskEventName::TaskLog.as_str(),
                TaskLogPayload {
                    message: trimmed.to_string(),
                },
            );
        }
    });
}
