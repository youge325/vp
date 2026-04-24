use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::{io, process::ExitStatus, process::Stdio, time::Duration};

use command_group::{AsyncCommandGroup, AsyncGroupChild};
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager, Runtime, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::{mpsc, oneshot};
use tokio::time::MissedTickBehavior;

use crate::models::{
    RunningTask, TaskCompletedPayload, TaskControlKind, TaskControlMessage, TaskErrorPayload,
    TaskLogPayload, TaskProgressPayload, TaskRequest, TaskState,
};
use crate::process_control;
use crate::runtime::{build_env_map, resolve_runtime_paths};

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

    let mut child = command
        .group_spawn()
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

    command.current_dir(&paths.backend_dir);
    command.envs(build_env_map(paths));
    Ok(command)
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

            if let Ok(value) = serde_json::from_str::<Value>(trimmed) {
                match value
                    .get("type")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                {
                    "progress" => {
                        let payload = TaskProgressPayload {
                            current: value.get("current").and_then(Value::as_u64).unwrap_or(0),
                            total: value.get("total").and_then(Value::as_u64).unwrap_or(0),
                            percent: value.get("percent").and_then(Value::as_f64).unwrap_or(0.0),
                            stage: value
                                .get("stage")
                                .and_then(Value::as_str)
                                .unwrap_or_default()
                                .to_string(),
                            stage_index: value
                                .get("stage_index")
                                .and_then(Value::as_u64)
                                .unwrap_or(1),
                            stage_total: value
                                .get("stage_total")
                                .and_then(Value::as_u64)
                                .unwrap_or(1),
                        };
                        let _ = app.emit("task-progress", payload);
                    }
                    "completed" => {
                        terminal_sent.store(true, Ordering::SeqCst);
                        let payload = TaskCompletedPayload {
                            output_path: value
                                .get("output_path")
                                .and_then(Value::as_str)
                                .unwrap_or_default()
                                .to_string(),
                            processed_frames: value
                                .get("processed_frames")
                                .and_then(Value::as_u64)
                                .unwrap_or(0),
                            time_seconds: value
                                .get("time_seconds")
                                .and_then(Value::as_f64)
                                .unwrap_or(0.0),
                        };
                        let _ = app.emit("task-completed", payload);
                    }
                    "error" => {
                        terminal_sent.store(true, Ordering::SeqCst);
                        let payload = TaskErrorPayload {
                            code: value
                                .get("code")
                                .and_then(Value::as_str)
                                .unwrap_or("process_failed")
                                .to_string(),
                            message: value
                                .get("message")
                                .and_then(Value::as_str)
                                .unwrap_or("Backend process failed.")
                                .to_string(),
                            details: value.get("details").cloned(),
                        };
                        let _ = app.emit("task-error", payload);
                    }
                    _ => {
                        let _ = app.emit(
                            "task-log",
                            TaskLogPayload {
                                message: trimmed.to_string(),
                            },
                        );
                    }
                }
            } else {
                let _ = app.emit(
                    "task-log",
                    TaskLogPayload {
                        message: trimmed.to_string(),
                    },
                );
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
                "task-log",
                TaskLogPayload {
                    message: trimmed.to_string(),
                },
            );
        }
    });
}

fn spawn_task_controller<R: Runtime + 'static>(
    app: AppHandle<R>,
    mut child: AsyncGroupChild,
    root_pid: u32,
    mut control_rx: mpsc::Receiver<TaskControlMessage>,
    terminal_sent: Arc<std::sync::atomic::AtomicBool>,
) {
    tauri::async_runtime::spawn(async move {
        let mut was_cancelled = false;
        let mut is_paused = false;
        let mut control_rx_closed = false;
        let mut ticker = tokio::time::interval(Duration::from_millis(120));
        ticker.set_missed_tick_behavior(MissedTickBehavior::Skip);
        let status: io::Result<ExitStatus>;

        loop {
            tokio::select! {
                maybe_message = control_rx.recv(), if !control_rx_closed => {
                    let Some(message) = maybe_message else {
                        control_rx_closed = true;
                        continue;
                    };
                    let result = handle_task_control(
                        &mut child,
                        root_pid,
                        message.kind,
                        &mut was_cancelled,
                        &mut is_paused,
                    );
                    let _ = message.response.send(result);
                }
                _ = ticker.tick() => {
                    match child.try_wait() {
                        Ok(Some(exit_status)) => {
                            status = Ok(exit_status);
                            break;
                        }
                        Ok(None) => {}
                        Err(error) => {
                            status = Err(error);
                            break;
                        }
                    }
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
                    let _ = app.emit("task-cancelled", ());
                    return;
                }

                if !exit_status.success() && !terminal_sent {
                    let _ = app.emit(
                        "task-error",
                        TaskErrorPayload {
                            code: "process_failed".to_string(),
                            message: format!("Backend process exited with status {}.", exit_status),
                            details: None,
                        },
                    );
                }
            }
            Err(error) => {
                if was_cancelled {
                    let _ = app.emit("task-cancelled", ());
                } else if !terminal_sent {
                    let _ = app.emit(
                        "task-error",
                        TaskErrorPayload {
                            code: "process_failed".to_string(),
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
    child: &mut AsyncGroupChild,
    root_pid: u32,
    kind: TaskControlKind,
    was_cancelled: &mut bool,
    is_paused: &mut bool,
) -> Result<(), String> {
    match kind {
        TaskControlKind::Cancel => {
            *was_cancelled = true;
            if *is_paused {
                let _ = process_control::resume_process_tree(root_pid);
                *is_paused = false;
            }
            match child.start_kill() {
                Ok(()) => Ok(()),
                Err(error) if error.kind() == io::ErrorKind::InvalidInput => Ok(()),
                Err(error) => Err(format!("Unable to cancel task: {error}")),
            }
        }
        TaskControlKind::Pause => {
            if *was_cancelled {
                return Err("The task is already being cancelled.".to_string());
            }
            if *is_paused {
                return Ok(());
            }
            process_control::suspend_process_tree(root_pid)?;
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
            process_control::resume_process_tree(root_pid)?;
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
