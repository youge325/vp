//! ``spawn_task`` — launch the long-running ``process`` subcommand.
//!
//! Owns the end-to-end orchestration: reserve the task slot, build the
//! child command, push the config
//! payload through stdin, hand stdout/stderr to the readers, and
//! delegate cancel / pause / resume to the controller actor.
//!
//! The Tauri command wrapper forwards plain references so orchestration
//! remains testable without constructing Tauri state handles.

use std::io;
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use command_group::AsyncGroupChild;
use tauri::{AppHandle, Runtime};
use tokio::sync::mpsc;

use crate::error::ShellError;
use crate::models::TaskRequest;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{build_process_command, spawn_no_window_group};
use crate::tasks::controller::{spawn_task_supervisor, TaskSupervisorSession};
use crate::tasks::readers::{
    spawn_stderr_reader, spawn_stdin_writer, spawn_stdout_reader, ProgressBeat,
};
use crate::tasks::state::TaskState;
use crate::tasks::stderr::StderrCapture;
use crate::tasks::TaskApplicationError;

const FAILED_START_CLEANUP_TIMEOUT: Duration = Duration::from_secs(5);

async fn terminate_failed_start(child: &mut AsyncGroupChild) -> Result<(), ShellError> {
    let kill_error = child.start_kill().err();
    let wait_for_exit = async {
        loop {
            match child.try_wait() {
                Ok(Some(_)) => return Ok(()),
                Ok(None) => tokio::time::sleep(Duration::from_millis(20)).await,
                Err(error) => return Err(error),
            }
        }
    };
    match tokio::time::timeout(FAILED_START_CLEANUP_TIMEOUT, wait_for_exit).await {
        Ok(Ok(())) => Ok(()),
        Ok(Err(wait_error)) => Err(ShellError::Io(io::Error::other(format!(
            "failed to reap backend after start failure: {wait_error}; kill error: {kill_error:?}"
        )))),
        Err(_) => Err(ShellError::Io(io::Error::new(
            io::ErrorKind::TimedOut,
            format!("timed out reaping backend after start failure; kill error: {kill_error:?}"),
        ))),
    }
}

pub(crate) async fn spawn_task<R: Runtime>(
    app: AppHandle<R>,
    state: &TaskState,
    paths: &ResolvedRuntimePaths,
    request: TaskRequest,
) -> Result<(), TaskApplicationError> {
    // Reserve before building or spawning anything. A concurrent start is
    // rejected without creating an orphan backend process.
    let lease = state.reserve_start().await?;

    let (mut command, stdin_payload) = match build_process_command(paths, &request) {
        Ok(command) => command,
        Err(error) => {
            state.rollback_start(&lease).await;
            return Err(ShellError::SchemaValidation(format!(
                "Unable to encode backend process configuration: {error}"
            ))
            .into());
        }
    };
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    // ``build_process_command`` already set ``Stdio::piped()`` on stdin so the
    // payload can be fed in immediately after spawn.

    let mut child = match spawn_no_window_group(&mut command) {
        Ok(child) => child,
        Err(error) => {
            state.rollback_start(&lease).await;
            return Err(ShellError::Spawn(error).into());
        }
    };

    let Some(stdin) = child.inner().stdin.take() else {
        let cleanup = terminate_failed_start(&mut child).await;
        state.rollback_start(&lease).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stdin.".to_string()).into(),
        );
    };

    let Some(stdout) = child.inner().stdout.take() else {
        let cleanup = terminate_failed_start(&mut child).await;
        state.rollback_start(&lease).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stdout.".to_string()).into(),
        );
    };
    let Some(stderr) = child.inner().stderr.take() else {
        let cleanup = terminate_failed_start(&mut child).await;
        state.rollback_start(&lease).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stderr.".to_string()).into(),
        );
    };
    let Some(root_pid) = child.id() else {
        let cleanup = terminate_failed_start(&mut child).await;
        state.rollback_start(&lease).await;
        cleanup?;
        return Err(ShellError::RuntimeResolution(
            "Unable to resolve backend process id.".to_string(),
        )
        .into());
    };

    let cancel_token = lease.cancellation_token();
    let stderr_capture = StderrCapture::new();
    let progress_beat: ProgressBeat = Arc::new(Mutex::new(Instant::now()));
    let (control_tx, control_rx) = mpsc::channel(8);

    if let Err(error) = state.activate(&lease, control_tx).await {
        let cleanup = terminate_failed_start(&mut child).await;
        state.rollback_start(&lease).await;
        cleanup?;
        return Err(error.into());
    }

    let (output_tx, output_rx) = mpsc::channel(64);
    // Start both readers before writing a potentially large config. This prevents the classic
    // three-pipe deadlock where Python logs enough output to fill stdout/stderr before it reads
    // stdin while the host is itself blocked writing that stdin payload.
    let stdout_reader = spawn_stdout_reader(stdout, output_tx.clone(), progress_beat.clone());
    let stderr_reader = spawn_stderr_reader(stderr, output_tx.clone(), stderr_capture.clone());
    let stdin_writer = spawn_stdin_writer(stdin, stdin_payload, output_tx.clone());
    drop(output_tx);

    spawn_task_supervisor(TaskSupervisorSession {
        app,
        child,
        lease,
        root_pid,
        control_rx,
        output_rx,
        stdin_writer,
        stdout_reader,
        stderr_reader,
        stderr_capture,
        cancel_token,
        progress_beat,
    });
    Ok(())
}
