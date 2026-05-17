//! ``spawn_task`` — launch the long-running ``process`` subcommand.
//!
//! Split out of the legacy ``tasks::runner`` mod in Phase 5b. Owns the
//! end-to-end orchestration: build the child command, push the config
//! payload through stdin, hand stdout/stderr to the readers, and
//! delegate cancel / pause / resume to the controller actor.
//!
//! Phase 5b also flipped the signature from ``State<'_, TaskState>`` /
//! ``State<'_, ResolvedRuntimePaths>`` to plain references. The Tauri
//! command wrappers in [`crate::tasks::commands`] now call ``.inner()``
//! and forward the borrow; the change makes the function callable from
//! unit / integration tests that don't have access to a real
//! ``tauri::State`` handle.

use std::process::Stdio;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use tauri::{AppHandle, Runtime};
use tokio::io::AsyncWriteExt;
use tokio::sync::mpsc;

use crate::error::ShellError;
use crate::models::TaskRequest;
use crate::process_control;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{build_process_command, spawn_no_window_group};
use crate::tasks::cancellation::CancellationToken;
use crate::tasks::controller::{spawn_task_controller, WatchdogConfig};
use crate::tasks::handle::TaskHandle;
use crate::tasks::readers::{spawn_stderr_reader, spawn_stdout_reader, ProgressBeat};
use crate::tasks::state::TaskState;
use crate::tasks::stderr::StderrCapture;

pub async fn spawn_task<R: Runtime>(
    app: AppHandle<R>,
    state: &TaskState,
    paths: &ResolvedRuntimePaths,
    request: TaskRequest,
) -> Result<(), ShellError> {
    // Fast-path peek so we don't pay for a fork+exec when there's
    // obviously a task already running. The authoritative atomic
    // check happens inside [`TaskState::try_start`] further down.
    if !state.is_idle().await {
        return Err(ShellError::InvalidInput(
            "A task is already running.".to_string(),
        ));
    }

    let (mut command, stdin_payload) =
        build_process_command(paths, &request).map_err(ShellError::from)?;
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    // ``build_process_command`` already set ``Stdio::piped()`` on stdin so the
    // payload can be fed in immediately after spawn — see Phase D.3.1.

    let mut child = spawn_no_window_group(&mut command).map_err(ShellError::Spawn)?;

    // Phase D.3.1 — push the config payload through stdin, then drop the
    // handle to signal EOF. Doing this before reading stdout/stderr keeps
    // the child unblocked even if the process group started fast.
    if let Some(mut stdin) = child.inner().stdin.take() {
        if !stdin_payload.is_empty() {
            let _ = stdin.write_all(stdin_payload.as_bytes()).await;
            let _ = stdin.flush().await;
        }
        // Explicit drop to close the pipe (signals EOF to the child).
        drop(stdin);
    }

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

    // Phase 5d — atomic Idle → Running. If the fast peek above
    // raced another spawn we tear the freshly-spawned child down
    // here rather than orphaning it; without this transition the
    // state machine would have both ``Running { handle }`` slots
    // and we'd lose the previous task's cancel/pause handle.
    if let Err(error) = state.try_start(handle).await {
        let _ = child.kill().await;
        return Err(error);
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
        process_control::default_controller(),
        WatchdogConfig::from_env(),
    );
    Ok(())
}
