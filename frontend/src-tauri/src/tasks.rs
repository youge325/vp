use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::{io, process::ExitStatus, process::Stdio};

use command_group::{AsyncCommandGroup, AsyncGroupChild};
use serde::Deserialize;
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager, Runtime, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::{mpsc, oneshot};

use crate::models::{
    ResumeStatusPayload, RunningTask, TaskCompletedPayload, TaskControlKind, TaskControlMessage,
    TaskErrorPayload, TaskLogPayload, TaskProgressPayload, TaskRequest, TaskState,
};
use crate::protocol::TaskEventName;
use crate::runtime::{build_env_map, resolve_runtime_paths};

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum NdjsonEnvelope {
    #[serde(rename = "progress")]
    Progress(TaskProgressPayload),
    #[serde(rename = "completed")]
    Completed(TaskCompletedPayload),
    #[serde(rename = "error")]
    Error(TaskErrorPayload),
    #[serde(rename = "resume_status")]
    ResumeStatus(ResumeStatusPayload),
}

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;

pub async fn run_single_cli_command<R: Runtime>(
    app: &AppHandle<R>,
    args: &[String],
) -> Result<Value, String> {
    let paths = resolve_runtime_paths(app)?;
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app"]);
    command.args(args);
    command.current_dir(&paths.backend_dir);
    command.stdin(Stdio::null());
    command.envs(build_env_map(&paths));
    apply_no_window(&mut command);

    let output = command
        .output()
        .await
        .map_err(|error| format!("Unable to run backend CLI: {error}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !output.status.success() {
        if let Some(value) = parse_last_json_line(&stdout) {
            return Ok(value);
        }
        return Err(format!(
            "Backend command failed: {}",
            stderr.trim().trim_matches('"')
        ));
    }

    parse_last_json_line(&stdout).ok_or_else(|| "Backend CLI did not emit JSON output.".to_string())
}

pub async fn spawn_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    request: TaskRequest,
) -> Result<(), String> {
    {
        let guard = state.current.lock().await;
        if guard.is_some() {
            return Err("A task is already running.".to_string());
        }
    }

    let paths = resolve_runtime_paths(&app)?;
    let mut command = build_process_command(&paths, &request).map_err(|error| error.to_string())?;
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    command.stdin(Stdio::null());

    let mut child = spawn_no_window_group(&mut command)
        .map_err(|error| format!("Unable to start backend process: {error}"))?;

    let stdout = child
        .inner()
        .stdout
        .take()
        .ok_or_else(|| "Unable to capture backend stdout.".to_string())?;
    let stderr = child
        .inner()
        .stderr
        .take()
        .ok_or_else(|| "Unable to capture backend stderr.".to_string())?;

    let root_pid = child
        .id()
        .ok_or_else(|| "Unable to resolve backend process id.".to_string())?;
    let terminal_sent = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let (control_tx, control_rx) = mpsc::channel(8);
    let running = RunningTask { control_tx };

    {
        let mut guard = state.current.lock().await;
        *guard = Some(running.clone());
    }

    spawn_stdout_reader(app.clone(), stdout, terminal_sent.clone());
    spawn_stderr_reader(app.clone(), stderr);
    spawn_task_controller(app, child, root_pid, control_rx, terminal_sent);
    Ok(())
}

pub async fn cancel_running_task(state: State<'_, TaskState>) -> Result<(), String> {
    send_task_control(state, TaskControlKind::Cancel).await
}

pub async fn pause_running_task(state: State<'_, TaskState>) -> Result<(), String> {
    send_task_control(state, TaskControlKind::Pause).await
}

pub async fn resume_running_task(state: State<'_, TaskState>) -> Result<(), String> {
    send_task_control(state, TaskControlKind::Resume).await
}

async fn send_task_control(
    state: State<'_, TaskState>,
    kind: TaskControlKind,
) -> Result<(), String> {
    let running = {
        let guard = state.current.lock().await;
        guard
            .clone()
            .ok_or_else(|| "There is no running task.".to_string())?
    };

    let (response_tx, response_rx) = oneshot::channel();
    running
        .control_tx
        .send(TaskControlMessage {
            kind,
            response: response_tx,
        })
        .await
        .map_err(|_| "The running task controller is unavailable.".to_string())?;

    response_rx
        .await
        .map_err(|_| "The running task controller stopped before replying.".to_string())?
}

fn build_process_command(
    paths: &crate::runtime::ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<Command, serde_json::Error> {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", "process"]);
    command.args(["--input", &request.input_path]);

    let decode_json = serde_json::to_string(&request.decode_config)?;
    let workflow_json = serde_json::to_string(&request.workflow_config)?;
    let encode_json = serde_json::to_string(&request.encode_config)?;
    let output_json = serde_json::to_string(&request.output_config)?;

    command.args(["--decode-config-json", &decode_json]);
    command.args(["--workflow-config-json", &workflow_json]);
    command.args(["--encode-config-json", &encode_json]);
    command.args(["--output-config-json", &output_json]);

    if let Some(mode) = request.resume_mode.as_deref() {
        if !mode.is_empty() {
            command.args(["--resume-mode", mode]);
        }
    }

    command.current_dir(&paths.backend_dir);
    command.envs(build_env_map(paths));
    Ok(command)
}

pub fn build_inspect_output_args(request: &TaskRequest) -> Result<Vec<String>, serde_json::Error> {
    let mut args = vec![
        String::from("inspect-output"),
        String::from("--input"),
        request.input_path.clone(),
    ];

    args.push(String::from("--decode-config-json"));
    args.push(serde_json::to_string(&request.decode_config)?);
    args.push(String::from("--workflow-config-json"));
    args.push(serde_json::to_string(&request.workflow_config)?);
    args.push(String::from("--encode-config-json"));
    args.push(serde_json::to_string(&request.encode_config)?);
    args.push(String::from("--output-config-json"));
    args.push(serde_json::to_string(&request.output_config)?);

    Ok(args)
}

#[cfg(windows)]
fn apply_no_window(command: &mut Command) {
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
fn apply_no_window(_command: &mut Command) {}

#[cfg(windows)]
fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.group().creation_flags(CREATE_NO_WINDOW).spawn()
}

#[cfg(not(windows))]
fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.group_spawn()
}

fn spawn_stdout_reader<R: Runtime + 'static>(
    app: AppHandle<R>,
    stdout: tokio::process::ChildStdout,
    terminal_sent: Arc<std::sync::atomic::AtomicBool>,
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
) {
    tauri::async_runtime::spawn(async move {
        let mut lines = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            let _ = app.emit(
                TaskEventName::TaskLog.as_str(),
                TaskLogPayload {
                    message: trimmed.to_string(),
                },
            );
        }
    });
}

fn spawn_task_controller<R: Runtime + 'static>(
    app: AppHandle<R>,
    child: AsyncGroupChild,
    root_pid: u32,
    mut control_rx: mpsc::Receiver<TaskControlMessage>,
    terminal_sent: Arc<std::sync::atomic::AtomicBool>,
) {
    let controller: Arc<dyn crate::process_control::ProcessController> =
        crate::process_control::default_controller();

    // Channel for the controller to signal kill to the wait task.
    let (kill_tx, mut kill_rx) = mpsc::channel::<()>(1);
    // Oneshot for the wait task to report the child exit status.
    let (exit_tx, mut exit_rx) = oneshot::channel::<io::Result<ExitStatus>>();

    // Spawn the child-wait task.  It owns the AsyncGroupChild and waits
    // either for a natural exit or for a kill signal from the controller.
    tauri::async_runtime::spawn(async move {
        let mut child = child;
        tokio::select! {
            _ = kill_rx.recv() => {
                // Cancel requested: kill the entire process group then reap.
                let _ = child.kill().await;
                let status = child.wait().await;
                let _ = exit_tx.send(status);
            }
            status = child.wait() => {
                // Natural exit.
                let _ = exit_tx.send(status);
            }
        }
    });

    // Controller task: handles Pause / Resume / Cancel and waits for exit.
    tauri::async_runtime::spawn(async move {
        let mut was_cancelled = false;
        let mut is_paused = false;
        let mut control_rx_closed = false;
        let status: io::Result<ExitStatus>;

        loop {
            tokio::select! {
                maybe_message = control_rx.recv(), if !control_rx_closed => {
                    let Some(message) = maybe_message else {
                        control_rx_closed = true;
                        continue;
                    };
                    let result = handle_task_control(
                        &*controller,
                        &kill_tx,
                        root_pid,
                        message.kind,
                        &mut was_cancelled,
                        &mut is_paused,
                    );
                    let _ = message.response.send(result);
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

        let terminal_sent = terminal_sent.load(Ordering::SeqCst);

        match status {
            Ok(exit_status) => {
                if was_cancelled {
                    let _ = app.emit(TaskEventName::TaskCancelled.as_str(), ());
                    return;
                }

                if !exit_status.success() && !terminal_sent {
                    let _ = app.emit(
                        TaskEventName::TaskError.as_str(),
                        TaskErrorPayload {
                            code: crate::protocol::TaskErrorCode::ProcessFailed,
                            message: format!("Backend process exited with status {}.", exit_status),
                            details: None,
                        },
                    );
                }
            }
            Err(error) => {
                if was_cancelled {
                    let _ = app.emit(TaskEventName::TaskCancelled.as_str(), ());
                } else if !terminal_sent {
                    let _ = app.emit(
                        TaskEventName::TaskError.as_str(),
                        TaskErrorPayload {
                            code: crate::protocol::TaskErrorCode::ProcessFailed,
                            message: format!("Failed while waiting for backend process: {error}"),
                            details: None,
                        },
                    );
                }
            }
        }
    });
}

fn handle_task_control(
    controller: &dyn crate::process_control::ProcessController,
    kill_tx: &mpsc::Sender<()>,
    root_pid: u32,
    kind: TaskControlKind,
    was_cancelled: &mut bool,
    is_paused: &mut bool,
) -> Result<(), String> {
    match kind {
        TaskControlKind::Cancel => {
            *was_cancelled = true;
            if *is_paused {
                let _ = controller.resume(root_pid);
                *is_paused = false;
            }
            // Signal the wait task to kill the child group.
            let _ = kill_tx.try_send(());
            Ok(())
        }
        TaskControlKind::Pause => {
            if *was_cancelled {
                return Err("The task is already being cancelled.".to_string());
            }
            if *is_paused {
                return Ok(());
            }
            controller.suspend(root_pid)?;
            *is_paused = true;
            Ok(())
        }
        TaskControlKind::Resume => {
            if *was_cancelled {
                return Err("The task is already being cancelled.".to_string());
            }
            if !*is_paused {
                return Ok(());
            }
            controller.resume(root_pid)?;
            *is_paused = false;
            Ok(())
        }
    }
}

pub fn parse_last_json_line(stdout: &str) -> Option<Value> {
    stdout
        .lines()
        .rev()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .and_then(|line| serde_json::from_str::<Value>(line).ok())
}

#[cfg(test)]
mod tests {
    use super::parse_last_json_line;

    #[test]
    fn parses_last_json_line() {
        let stdout = "noise\n{\"type\":\"check\",\"ffmpeg\":{\"available\":true}}\n";
        let parsed = parse_last_json_line(stdout).expect("json");
        assert_eq!(parsed["type"], "check");
    }
}

pub mod commands;
