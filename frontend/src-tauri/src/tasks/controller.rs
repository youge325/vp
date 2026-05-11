use std::io;
use std::process::ExitStatus;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use command_group::AsyncGroupChild;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::{mpsc, oneshot};

use crate::models::TaskErrorPayload;
use crate::process_control::{self, ProcessController};
use crate::protocol::TaskEventName;
use crate::tasks::state::{TaskControlKind, TaskControlMessage, TaskState};

pub fn spawn_task_controller<R: Runtime + 'static>(
    app: AppHandle<R>,
    child: AsyncGroupChild,
    root_pid: u32,
    mut control_rx: mpsc::Receiver<TaskControlMessage>,
    terminal_sent: Arc<AtomicBool>,
) {
    let controller: Arc<dyn ProcessController> = process_control::default_controller();

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
                let _ = child.kill().await;
                let status = child.wait().await;
                let _ = exit_tx.send(status);
            }
            status = child.wait() => {
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
    controller: &dyn ProcessController,
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
