//! ``spawn_task`` — launch the long-running ``process`` subcommand.
//!
//! Owns the end-to-end orchestration: reserve the task slot, build the
//! child command, push the config
//! payload through stdin, hand stdout/stderr to the readers, and
//! delegate cancel / pause / resume to the controller actor.
//!
//! The Tauri command wrapper forwards plain references so orchestration
//! remains testable without constructing Tauri state handles.

use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use tauri::{AppHandle, Runtime};
use tokio::sync::mpsc;

use crate::error::ShellError;
use crate::generated::{BackendProcessSpec, StartTaskSpec};
use crate::models::TaskRequest;
use crate::process_control::ProcessController;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{build_process_command, spawn_no_window_group};
use crate::tasks::cleanup::own_late_cleanup;
use crate::tasks::controller::{spawn_task_supervisor, TaskSupervisorSession};
use crate::tasks::ports::{TaskEventSink, TaskLifecyclePort, TauriTaskPorts};
use crate::tasks::readers::{
    spawn_stderr_reader, spawn_stdin_writer, spawn_stdout_reader, ProgressBeat,
};
use crate::tasks::state::{StartLease, TaskState};
use crate::tasks::stderr::StderrCapture;
use crate::tasks::subprocess::{ProcessGroupChild, ProcessGroupOwner};
use crate::tasks::TaskApplicationError;

async fn terminate_failed_start<R: Runtime + 'static>(
    app: &AppHandle<R>,
    state: &TaskState,
    lease: &StartLease,
    child: ProcessGroupChild,
) -> Result<(), ShellError> {
    let owns_start = state.begin_start_cleanup(lease).await;
    let (mut owner, ticket) = ProcessGroupOwner::new(child, "backend after task start failure");
    let cleanup = owner
        .terminate_and_reap(StartTaskSpec::TERMINATION_TIMEOUT)
        .await;
    drop(owner);
    match cleanup {
        Ok(()) => {
            if owns_start && !state.finish_once(lease, || {}).await {
                return Err(ShellError::Io(std::io::Error::other(
                    "task start cleanup lost lifecycle ownership after reaping the backend",
                )));
            }
            Ok(())
        }
        Err(message) => {
            if owns_start {
                if !state.fail_cleanup_once(lease, || {}).await {
                    eprintln!("task start cleanup no longer owns its lifecycle lease");
                }
                let lifecycle: Arc<dyn TaskLifecyclePort> =
                    Arc::new(TauriTaskPorts::new(app.clone()));
                own_late_cleanup(lifecycle, lease.clone(), ticket, None).await;
            }
            Err(ShellError::Io(std::io::Error::other(message)))
        }
    }
}

pub(crate) async fn spawn_task<R: Runtime + 'static>(
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
            let (source, child) = error.into_parts();
            if let Some(child) = child {
                terminate_failed_start(&app, state, &lease, child).await?;
            } else {
                state.rollback_start(&lease).await;
            }
            return Err(ShellError::Spawn(source).into());
        }
    };
    let Some(root_pid) = child.id() else {
        let cleanup = terminate_failed_start(&app, state, &lease, child).await;
        cleanup?;
        return Err(ShellError::RuntimeResolution(
            "Unable to resolve backend process id.".to_string(),
        )
        .into());
    };
    let process_controller: Arc<dyn crate::process_control::ProcessControl> =
        match ProcessController::new(root_pid) {
            Ok(controller) => Arc::new(controller),
            Err(error) => {
                let cleanup = terminate_failed_start(&app, state, &lease, child).await;
                cleanup?;
                return Err(ShellError::ProcessControl(error).into());
            }
        };

    let Some(stdin) = child.inner().stdin.take() else {
        let cleanup = terminate_failed_start(&app, state, &lease, child).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stdin.".to_string()).into(),
        );
    };

    let Some(stdout) = child.inner().stdout.take() else {
        let cleanup = terminate_failed_start(&app, state, &lease, child).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stdout.".to_string()).into(),
        );
    };
    let Some(stderr) = child.inner().stderr.take() else {
        let cleanup = terminate_failed_start(&app, state, &lease, child).await;
        cleanup?;
        return Err(
            ShellError::RuntimeResolution("Unable to capture backend stderr.".to_string()).into(),
        );
    };
    let cancel_token = lease.cancellation_token();
    let stderr_capture = StderrCapture::new();
    let progress_beat: ProgressBeat = Arc::new(Mutex::new(Instant::now()));
    let (control_tx, control_rx) = mpsc::channel(8);

    if let Err(error) = state.activate(&lease, control_tx).await {
        let cleanup = terminate_failed_start(&app, state, &lease, child).await;
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

    let tauri_ports = Arc::new(TauriTaskPorts::new(app));
    let event_sink: Arc<dyn TaskEventSink> = tauri_ports.clone();
    let lifecycle: Arc<dyn TaskLifecyclePort> = tauri_ports;
    spawn_task_supervisor(TaskSupervisorSession {
        event_sink,
        lifecycle,
        child,
        lease,
        process_controller,
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
