use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde_json::Value;
use tauri::{AppHandle, Emitter, Runtime, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::{mpsc, oneshot};

use crate::error::ShellError;
use crate::models::{TaskLogPayload, TaskRequest};
use crate::protocol::TaskEventName;
use crate::runtime::{build_env_map, resolve_runtime_paths};
use crate::tasks::builder::{apply_no_window, build_process_command, spawn_no_window_group};
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::controller::spawn_task_controller;
use crate::tasks::envelope::{parse_last_json_line, NdjsonEnvelope};
use crate::tasks::handle::TaskHandle;
use crate::tasks::state::{TaskControlKind, TaskControlMessage, TaskState};
use crate::tasks::stderr::StderrCapture;

pub type ProgressBeat = Arc<Mutex<Instant>>;

pub async fn run_single_cli_command<R: Runtime>(
    app: &AppHandle<R>,
    args: &[String],
) -> Result<Value, ShellError> {
    let paths = resolve_runtime_paths(app)?;
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app"]);
    command.args(args);
    command.current_dir(&paths.backend_dir);
    command.stdin(Stdio::null());
    command.envs(build_env_map(&paths));
    apply_no_window(&mut command);

    let output = command.output().await.map_err(ShellError::Spawn)?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !output.status.success() {
        if let Some(value) = parse_last_json_line(&stdout) {
            return Ok(value);
        }
        return Err(ShellError::BackendExit(format!(
            "Backend command failed: {}",
            stderr.trim().trim_matches('"')
        )));
    }

    parse_last_json_line(&stdout).ok_or_else(|| {
        ShellError::BackendExit("Backend CLI did not emit JSON output.".to_string())
    })
}

pub async fn spawn_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    request: TaskRequest,
) -> Result<(), ShellError> {
    {
        let guard = state.current.lock().await;
        if guard.is_some() {
            return Err(ShellError::InvalidInput(
                "A task is already running.".to_string(),
            ));
        }
    }

    let paths = resolve_runtime_paths(&app)?;
    let mut command = build_process_command(&paths, &request)?;
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    command.stdin(Stdio::null());

    let mut child = spawn_no_window_group(&mut command).map_err(ShellError::Spawn)?;

    let stdout = child.inner().stdout.take().ok_or_else(|| {
        ShellError::BackendExit("Unable to capture backend stdout.".to_string())
    })?;
    let stderr = child.inner().stderr.take().ok_or_else(|| {
        ShellError::BackendExit("Unable to capture backend stderr.".to_string())
    })?;

    let root_pid = child.id().ok_or_else(|| {
        ShellError::BackendExit("Unable to resolve backend process id.".to_string())
    })?;
    let terminal_sent = Arc::new(AtomicBool::new(false));
    let cancel_token = CancellationToken::new();
    let stderr_capture = StderrCapture::new();
    let progress_beat: ProgressBeat = Arc::new(Mutex::new(Instant::now()));
    let (control_tx, control_rx) = mpsc::channel(8);
    let handle = TaskHandle::new(control_tx, cancel_token.clone());

    {
        let mut guard = state.current.lock().await;
        *guard = Some(handle);
    }

    spawn_stdout_reader(
        app.clone(),
        stdout,
        terminal_sent.clone(),
        progress_beat.clone(),
    );
    spawn_stderr_reader(app.clone(), stderr, stderr_capture.clone());
    spawn_task_controller(
        app,
        child,
        root_pid,
        control_rx,
        terminal_sent,
        stderr_capture,
        cancel_token,
        progress_beat,
    );
    Ok(())
}

pub async fn cancel_running_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    let handle = {
        let guard = state.current.lock().await;
        guard.clone().ok_or(ShellError::NoActiveTask)?
    };
    // Cancellation is fire-and-forget. The controller will react via its
    // ``cancel_token.cancelled()`` branch, resume the child if it was
    // paused, kill it, and emit ``task-cancelled`` once the process exits.
    handle.cancel(CancelReason::User);
    Ok(())
}

pub async fn pause_running_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    send_task_control(state, TaskControlKind::Pause).await
}

pub async fn resume_running_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    send_task_control(state, TaskControlKind::Resume).await
}

async fn send_task_control(
    state: State<'_, TaskState>,
    kind: TaskControlKind,
) -> Result<(), ShellError> {
    let handle = {
        let guard = state.current.lock().await;
        guard.clone().ok_or(ShellError::NoActiveTask)?
    };

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
        .map_err(|_| {
            ShellError::BackendExit("The running task controller is unavailable.".to_string())
        })?;

    match response_rx.await {
        Ok(result) => result.map_err(ShellError::BackendExit),
        Err(_) => Err(ShellError::BackendExit(
            "The running task controller stopped before replying.".to_string(),
        )),
    }
}

fn spawn_stdout_reader<R: Runtime + 'static>(
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
                Err(_) => {
                    let _ = app.emit(
                        TaskEventName::TaskLog.as_str(),
                        TaskLogPayload {
                            message: trimmed.to_string(),
                        },
                    );
                }
            }
        }
    });
}

fn spawn_stderr_reader<R: Runtime + 'static>(
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
