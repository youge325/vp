use std::process::Stdio;
use std::sync::Arc;
use std::sync::atomic::Ordering;

use command_group::AsyncCommandGroup;
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager, Runtime, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::Mutex;

use crate::models::{
    RunningTask, TaskCompletedPayload, TaskErrorPayload, TaskLogPayload, TaskProgressPayload,
    TaskRequest, TaskState,
};
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
        return Err(format!("Backend command failed: {}", stderr.trim().trim_matches('"')));
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

    let child = Arc::new(Mutex::new(child));
    let running = RunningTask {
        child: child.clone(),
        cancelled: Arc::new(std::sync::atomic::AtomicBool::new(false)),
        terminal_sent: Arc::new(std::sync::atomic::AtomicBool::new(false)),
    };

    {
        let mut guard = state.current.lock().await;
        *guard = Some(running.clone());
    }

    spawn_stdout_reader(app.clone(), stdout, running.terminal_sent.clone());
    spawn_stderr_reader(app.clone(), stderr);
    spawn_waiter(app, running);
    Ok(())
}

pub async fn cancel_running_task(state: State<'_, TaskState>) -> Result<(), String> {
    let running = {
        let guard = state.current.lock().await;
        guard.clone().ok_or_else(|| "There is no running task.".to_string())?
    };

    running.cancelled.store(true, Ordering::SeqCst);
    let mut child = running.child.lock().await;
    child
        .kill()
        .await
        .map_err(|error| format!("Unable to cancel task: {error}"))?;
    Ok(())
}

fn build_process_command(
    paths: &crate::runtime::ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<Command, serde_json::Error> {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", "process"]);
    command.args(["--input", &request.input_path]);

    if let Some(output_path) = &request.output_path {
        if !output_path.is_empty() {
            command.args(["--output", output_path]);
        }
    }
    if let Some(temp_dir) = &request.temp_dir {
        if !temp_dir.is_empty() {
            command.args(["--temp-dir", temp_dir]);
        }
    }

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
                match value.get("type").and_then(Value::as_str).unwrap_or_default() {
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
                            stage_index: value.get("stage_index").and_then(Value::as_u64).unwrap_or(1),
                            stage_total: value.get("stage_total").and_then(Value::as_u64).unwrap_or(1),
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

fn spawn_stderr_reader<R: Runtime + 'static>(app: AppHandle<R>, stderr: tokio::process::ChildStderr) {
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

fn spawn_waiter<R: Runtime + 'static>(app: AppHandle<R>, running: RunningTask) {
    tauri::async_runtime::spawn(async move {
        let status = {
            let mut child = running.child.lock().await;
            child.wait().await
        };

        {
            let state = app.state::<TaskState>();
            let mut guard = state.current.lock().await;
            *guard = None;
        }

        let was_cancelled = running.cancelled.load(Ordering::SeqCst);
        let terminal_sent = running.terminal_sent.load(Ordering::SeqCst);

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
