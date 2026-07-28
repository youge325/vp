//! Structured owner for a running backend task.

use std::env;
use std::future::pending;
use std::future::Future;
use std::io;
use std::pin::Pin;
use std::process::ExitStatus;
use std::sync::Arc;
use std::task::{Context, Poll};
use std::time::Duration;

use command_group::AsyncGroupChild;
use tauri::async_runtime::JoinHandle;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::{mpsc, oneshot};

use crate::generated::TaskEventName;
use crate::models::{
    TaskCancelledPayload, TaskCancelledReason, TaskCompletedPayload, TaskErrorCode,
    TaskErrorPayload, TaskLogPayload,
};
use crate::process_control::{ProcessControl, ProcessControlError, ProcessController};
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::envelope::ClassifiedLine;
use crate::tasks::readers::{pipe_failure_payload, ProgressBeat, ReaderMessage};
use crate::tasks::state::StartLease;
use crate::tasks::stderr::StderrCapture;
use crate::tasks::{ProcessControlKind, TaskControlMessage, TaskState};

const DEFAULT_STALL_TIMEOUT_SECS: u64 = 600;
const DEFAULT_WATCHDOG_POLL_INTERVAL_SECS: u64 = 5;
const PIPE_DRAIN_TIMEOUT: Duration = Duration::from_secs(5);
// Leave one second for the controller result to traverse the oneshot before
// the IPC-side five-second response deadline expires.
const PROCESS_CONTROL_TIMEOUT: Duration = Duration::from_secs(4);
const TERMINAL_EXIT_GRACE: Duration = Duration::from_secs(5);
const CHILD_KILL_TIMEOUT: Duration = Duration::from_secs(5);
const CHILD_EXIT_POLL_INTERVAL: Duration = Duration::from_millis(50);
const STALL_TIMEOUT_ENV: &str = "VP_TASK_STALL_TIMEOUT_SECS";

pub(super) struct TaskSupervisorSession<R: Runtime> {
    pub(super) app: AppHandle<R>,
    pub(super) child: AsyncGroupChild,
    pub(super) lease: StartLease,
    pub(super) root_pid: u32,
    pub(super) control_rx: mpsc::Receiver<TaskControlMessage>,
    pub(super) output_rx: mpsc::Receiver<ReaderMessage>,
    pub(super) stdin_writer: JoinHandle<()>,
    pub(super) stdout_reader: JoinHandle<()>,
    pub(super) stderr_reader: JoinHandle<()>,
    pub(super) stderr_capture: StderrCapture,
    pub(super) cancel_token: CancellationToken,
    pub(super) progress_beat: ProgressBeat,
}

enum TerminalEvent {
    Completed(TaskCompletedPayload),
    BackendError(TaskErrorPayload),
    SupervisorError(TaskErrorPayload),
}

#[derive(Default)]
struct TerminalState {
    event: Option<TerminalEvent>,
}

impl TerminalState {
    fn has_event(&self) -> bool {
        self.event.is_some()
    }

    fn record_completed(&mut self, payload: TaskCompletedPayload) -> bool {
        if self.event.is_none() {
            self.event = Some(TerminalEvent::Completed(payload));
            false
        } else {
            self.record_supervisor_error(duplicate_terminal_payload("completed"));
            true
        }
    }

    fn record_backend_error(&mut self, payload: TaskErrorPayload) -> bool {
        if self.event.is_none() {
            self.event = Some(TerminalEvent::BackendError(payload));
            false
        } else {
            self.record_supervisor_error(duplicate_terminal_payload("error"));
            true
        }
    }

    fn record_supervisor_error(&mut self, payload: TaskErrorPayload) {
        if !matches!(self.event, Some(TerminalEvent::SupervisorError(_))) {
            self.event = Some(TerminalEvent::SupervisorError(payload));
        }
    }

    fn take(self) -> Option<TerminalEvent> {
        self.event
    }
}

struct AbortOnDropTask<T> {
    handle: JoinHandle<T>,
}

impl<T> AbortOnDropTask<T> {
    fn new(handle: JoinHandle<T>) -> Self {
        Self { handle }
    }

    fn abort(&self) {
        self.handle.abort();
    }
}

impl<T> Future for AbortOnDropTask<T> {
    type Output = tauri::Result<T>;

    fn poll(mut self: Pin<&mut Self>, context: &mut Context<'_>) -> Poll<Self::Output> {
        Pin::new(&mut self.handle).poll(context)
    }
}

impl<T> Drop for AbortOnDropTask<T> {
    fn drop(&mut self) {
        self.handle.abort();
    }
}

struct SupervisedChild {
    child: AsyncGroupChild,
}

impl SupervisedChild {
    fn new(child: AsyncGroupChild) -> Self {
        Self { child }
    }

    fn try_wait(&mut self) -> io::Result<Option<ExitStatus>> {
        self.child.try_wait()
    }

    fn start_kill(&mut self) -> io::Result<()> {
        self.child.start_kill()
    }
}

impl Drop for SupervisedChild {
    fn drop(&mut self) {
        // `start_kill` targets the entire command group/job synchronously. It is safe after a
        // completed wait (InvalidInput) and closes the last orphan window if the supervisor is
        // aborted or panics before reaching its normal terminal path.
        if self.child.id().is_some() {
            let _ = self.child.start_kill();
        }
    }
}

struct PendingControl {
    work: JoinHandle<(Result<(), ProcessControlError>, bool)>,
    deadline: Pin<Box<tokio::time::Sleep>>,
    timeout: Duration,
    timed_out: bool,
    response: Option<oneshot::Sender<Result<(), ProcessControlError>>>,
    initial_paused: bool,
    restore_target: Option<bool>,
    is_compensation: bool,
}

#[derive(Clone, Copy)]
enum ControlRestoration {
    Target(bool),
    Abandon,
}

enum PendingControlEvent {
    Finished(tauri::Result<(Result<(), ProcessControlError>, bool)>),
    TimedOut,
}

impl PendingControl {
    fn new<C: ProcessControl + 'static>(
        controller: Arc<C>,
        kind: ProcessControlKind,
        is_paused: bool,
        response: oneshot::Sender<Result<(), ProcessControlError>>,
        timeout: Duration,
    ) -> Self {
        Self {
            work: spawn_process_control_work(controller, kind, is_paused),
            deadline: Box::pin(tokio::time::sleep(timeout)),
            timeout,
            timed_out: false,
            response: Some(response),
            initial_paused: is_paused,
            restore_target: None,
            is_compensation: false,
        }
    }

    fn reject_response(&mut self, message: &str) {
        if let Some(response) = self.response.take() {
            let _ = response.send(Err(ProcessControlError::Worker(message.to_string())));
        }
    }

    fn timeout_response(&mut self) {
        self.timed_out = true;
        if !self.is_compensation {
            self.restore_target = Some(self.initial_paused);
        }
        self.reject_response(&format!(
            "operation timed out after {} seconds",
            self.timeout.as_secs_f64()
        ));
    }

    fn compensation<C: ProcessControl + 'static>(
        controller: Arc<C>,
        current_paused: bool,
        target_paused: bool,
    ) -> Self {
        let kind = if target_paused {
            ProcessControlKind::Pause
        } else {
            ProcessControlKind::Resume
        };
        Self {
            work: spawn_process_control_work(controller, kind, current_paused),
            deadline: Box::pin(tokio::time::sleep(PROCESS_CONTROL_TIMEOUT)),
            timeout: PROCESS_CONTROL_TIMEOUT,
            timed_out: false,
            response: None,
            initial_paused: target_paused,
            restore_target: None,
            is_compensation: true,
        }
    }

    fn apply_restoration(&mut self, restoration: ControlRestoration) {
        self.restore_target = match restoration {
            ControlRestoration::Target(target) => Some(target),
            ControlRestoration::Abandon => None,
        };
    }

    fn compensation_target(&self, next_paused: bool) -> Option<bool> {
        self.restore_target.filter(|target| next_paused != *target)
    }

    async fn wait(&mut self) -> PendingControlEvent {
        if self.timed_out {
            return PendingControlEvent::Finished((&mut self.work).await);
        }
        tokio::select! {
            result = &mut self.work => PendingControlEvent::Finished(result),
            _ = self.deadline.as_mut() => PendingControlEvent::TimedOut,
        }
    }
}

pub(super) fn spawn_task_supervisor<R: Runtime + 'static>(session: TaskSupervisorSession<R>) {
    tauri::async_runtime::spawn(run_task_supervisor(session));
}

async fn run_task_supervisor<R: Runtime + 'static>(session: TaskSupervisorSession<R>) {
    let TaskSupervisorSession {
        app,
        child,
        lease,
        root_pid,
        mut control_rx,
        mut output_rx,
        stdin_writer,
        stdout_reader,
        stderr_reader,
        stderr_capture,
        cancel_token,
        progress_beat,
    } = session;
    let mut child = SupervisedChild::new(child);
    let mut stdin_writer = AbortOnDropTask::new(stdin_writer);
    let mut stdout_reader = AbortOnDropTask::new(stdout_reader);
    let mut stderr_reader = AbortOnDropTask::new(stderr_reader);
    let process_controller = Arc::new(ProcessController::new(root_pid));

    let mut kill_deadline = None;
    let mut exit_status = None;
    let mut output_closed = false;
    let mut control_closed = false;
    let mut is_paused = false;
    let mut terminal = TerminalState::default();
    let mut terminal_deadline = None;
    let mut pending_control: Option<PendingControl> = None;
    let mut exit_poll = tokio::time::interval(CHILD_EXIT_POLL_INTERVAL);
    exit_poll.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    let stall_timeout = parse_stall_timeout();
    let mut watchdog = stall_timeout.map(|_| {
        let mut interval =
            tokio::time::interval(Duration::from_secs(DEFAULT_WATCHDOG_POLL_INTERVAL_SECS));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        interval
    });
    while exit_status.is_none() {
        tokio::select! {
            maybe_message = output_rx.recv(), if !output_closed => {
                match maybe_message {
                    Some(message) => {
                        let had_terminal = terminal.has_event();
                        let protocol_fatal = handle_reader_message(&app, message, &mut terminal);
                        if !had_terminal && terminal.has_event() {
                            let _ = app.state::<TaskState>().seal_owned(&lease).await;
                            close_control_channel(
                                &mut control_rx,
                                &mut control_closed,
                                &mut pending_control,
                                "process control was rejected because a terminal result was received",
                                ControlRestoration::Target(false),
                            );
                            if !protocol_fatal {
                                terminal_deadline = Some(Box::pin(tokio::time::sleep(TERMINAL_EXIT_GRACE)));
                            }
                        }
                        if protocol_fatal {
                            request_kill(
                                &mut child,
                                &mut kill_deadline,
                                &mut terminal,
                                &mut pending_control,
                                &mut control_rx,
                                &mut control_closed,
                            );
                        }
                    }
                    None => output_closed = true,
                }
            }
            maybe_control = control_rx.recv(), if !control_closed && pending_control.is_none() && kill_deadline.is_none() => {
                match maybe_control {
                    Some(message) => {
                        if !message.response.is_closed() {
                            pending_control = Some(PendingControl::new(
                                Arc::clone(&process_controller),
                                message.kind,
                                is_paused,
                                message.response,
                                PROCESS_CONTROL_TIMEOUT,
                            ));
                        }
                    }
                    None => control_closed = true,
                }
            }
            control_event = wait_for_pending_control(&mut pending_control), if pending_control.is_some() => {
                match control_event {
                    PendingControlEvent::Finished(control_result) => {
                        let mut pending = pending_control.take().expect("guarded pending control");
                        let (result, next_paused) = match control_result {
                            Ok(result) => result,
                            Err(error) => (
                                Err(ProcessControlError::Worker(error.to_string())),
                                is_paused,
                            ),
                        };
                        if pending.is_compensation && result.is_err() {
                            terminal.record_supervisor_error(TaskErrorPayload {
                                code: TaskErrorCode::ProcessFailed,
                                message: format!(
                                    "Unable to restore the backend pause state after an interrupted process-control operation: {}",
                                    result.as_ref().expect_err("checked error")
                                ),
                                details: None,
                            });
                            request_kill(
                                &mut child,
                                &mut kill_deadline,
                                &mut terminal,
                                &mut pending_control,
                                &mut control_rx,
                                &mut control_closed,
                            );
                        } else if let Some(target_paused) =
                            pending.compensation_target(next_paused)
                        {
                            is_paused = next_paused;
                            pending_control = Some(PendingControl::compensation(
                                Arc::clone(&process_controller),
                                is_paused,
                                target_paused,
                            ));
                        } else if result.is_ok() {
                            is_paused = next_paused;
                        }
                        if let Some(response) = pending.response.take() {
                            let _ = response.send(result);
                        }
                    }
                    PendingControlEvent::TimedOut => {
                        pending_control
                            .as_mut()
                            .expect("guarded pending control")
                            .timeout_response();
                    }
                }
            }
            _ = cancel_token.cancelled(), if kill_deadline.is_none() => {
                // Killing a stopped process group does not require first resuming it:
                // SIGKILL and the Windows job-object termination path both act on stopped tasks.
                request_kill(
                    &mut child,
                    &mut kill_deadline,
                    &mut terminal,
                    &mut pending_control,
                    &mut control_rx,
                    &mut control_closed,
                );
            }
            _ = exit_poll.tick() => {
                match child.try_wait() {
                    Ok(Some(status)) => {
                        let _ = app.state::<TaskState>().seal_owned(&lease).await;
                        exit_status = Some(Ok(status));
                        close_control_channel(
                            &mut control_rx,
                            &mut control_closed,
                            &mut pending_control,
                            "process control was cancelled because the backend exited",
                            ControlRestoration::Abandon,
                        );
                    }
                    Ok(None) => {}
                    Err(error) => {
                        let _ = app.state::<TaskState>().seal_owned(&lease).await;
                        exit_status = Some(Err(error));
                        close_control_channel(
                            &mut control_rx,
                            &mut control_closed,
                            &mut pending_control,
                            "process control was cancelled because backend status polling failed",
                            ControlRestoration::Abandon,
                        );
                    }
                }
            }
            _ = watchdog_tick(&mut watchdog), if kill_deadline.is_none() && !terminal.has_event() => {
                if let Some(timeout) = stall_timeout {
                    let stalled = progress_beat
                        .lock()
                        .ok()
                        .is_some_and(|beat| beat.elapsed() > timeout);
                    if stalled
                        && app
                            .state::<TaskState>()
                            .cancel_owned(&lease, CancelReason::Stalled)
                            .await
                    {
                        request_kill(
                            &mut child,
                            &mut kill_deadline,
                            &mut terminal,
                            &mut pending_control,
                            &mut control_rx,
                            &mut control_closed,
                        );
                    }
                }
            }
            _ = terminal_grace_tick(&mut terminal_deadline), if terminal_deadline.is_some() && kill_deadline.is_none() => {
                terminal.record_supervisor_error(TaskErrorPayload {
                    code: TaskErrorCode::ProcessFailed,
                    message: "Backend did not exit after emitting a terminal NDJSON envelope.".to_string(),
                    details: None,
                });
                request_kill(
                    &mut child,
                    &mut kill_deadline,
                    &mut terminal,
                    &mut pending_control,
                    &mut control_rx,
                    &mut control_closed,
                );
            }
            _ = terminal_grace_tick(&mut kill_deadline), if kill_deadline.is_some() => {
                match child.try_wait() {
                    Ok(Some(status)) => exit_status = Some(Ok(status)),
                    Ok(None) => {
                        terminal.record_supervisor_error(TaskErrorPayload {
                            code: TaskErrorCode::ProcessFailed,
                            message: "Timed out while waiting for the killed backend process group to exit.".to_string(),
                            details: None,
                        });
                        exit_status = Some(Err(io::Error::new(
                            io::ErrorKind::TimedOut,
                            "backend process group did not exit after kill",
                        )));
                    }
                    Err(error) => exit_status = Some(Err(error)),
                }
            }
        }
    }

    // On a synthetic kill timeout, dropping the kill-on-drop group handle is the final
    // best-effort termination path and also prevents the supervisor from leaking ownership.
    drop(child);

    // Keep ownership of an in-flight blocking control operation until its bounded wrapper
    // completes. Aborting a `spawn_blocking` join handle cannot stop the OS call and would turn
    // it into detached work; joining here preserves structured ownership without delaying kill.
    if let Some(mut pending) = pending_control.take() {
        let _ = (&mut pending.work).await;
        pending.apply_restoration(ControlRestoration::Abandon);
        pending.reject_response("process control finished after the backend stopped");
    }

    if !output_closed {
        let drain_result = tokio::time::timeout(PIPE_DRAIN_TIMEOUT, async {
            while let Some(message) = output_rx.recv().await {
                let _ = handle_reader_message(&app, message, &mut terminal);
            }
        })
        .await;
        if drain_result.is_err() {
            stdin_writer.abort();
            stdout_reader.abort();
            stderr_reader.abort();
            terminal.record_supervisor_error(TaskErrorPayload {
                code: TaskErrorCode::ProcessFailed,
                message: "Timed out while draining backend stdin/stdout/stderr.".to_string(),
                details: None,
            });
        }
    }

    for result in [
        (&mut stdin_writer).await,
        (&mut stdout_reader).await,
        (&mut stderr_reader).await,
    ] {
        if let Err(error) = result {
            terminal.record_supervisor_error(TaskErrorPayload {
                code: TaskErrorCode::ProcessFailed,
                message: format!("Backend pipe task failed: {error}"),
                details: None,
            });
        }
    }

    let status =
        exit_status.unwrap_or_else(|| Err(io::Error::other("backend exit status missing")));
    app.state::<TaskState>()
        .finish_once(&lease, || {
            emit_terminal_event(
                &app,
                status,
                terminal.take(),
                &cancel_token,
                &stderr_capture,
            );
        })
        .await;
}

async fn watchdog_tick(interval: &mut Option<tokio::time::Interval>) {
    match interval {
        Some(interval) => {
            interval.tick().await;
        }
        None => pending::<()>().await,
    }
}

async fn terminal_grace_tick(deadline: &mut Option<Pin<Box<tokio::time::Sleep>>>) {
    match deadline {
        Some(deadline) => deadline.as_mut().await,
        None => pending::<()>().await,
    }
}

async fn wait_for_pending_control(
    pending_control: &mut Option<PendingControl>,
) -> PendingControlEvent {
    match pending_control {
        Some(pending_control) => pending_control.wait().await,
        None => pending::<PendingControlEvent>().await,
    }
}

fn request_kill(
    child: &mut SupervisedChild,
    kill_deadline: &mut Option<Pin<Box<tokio::time::Sleep>>>,
    terminal: &mut TerminalState,
    pending_control: &mut Option<PendingControl>,
    control_rx: &mut mpsc::Receiver<TaskControlMessage>,
    control_closed: &mut bool,
) {
    if kill_deadline.is_some() {
        return;
    }
    close_control_channel(
        control_rx,
        control_closed,
        pending_control,
        "process control was cancelled because the task is stopping",
        ControlRestoration::Abandon,
    );
    if let Err(error) = child.start_kill() {
        if error.kind() != io::ErrorKind::InvalidInput {
            terminal.record_supervisor_error(TaskErrorPayload {
                code: TaskErrorCode::ProcessFailed,
                message: format!("Unable to kill the backend process group: {error}"),
                details: None,
            });
        }
    }
    *kill_deadline = Some(Box::pin(tokio::time::sleep(CHILD_KILL_TIMEOUT)));
}

fn close_control_channel(
    control_rx: &mut mpsc::Receiver<TaskControlMessage>,
    control_closed: &mut bool,
    pending_control: &mut Option<PendingControl>,
    message: &str,
    restoration: ControlRestoration,
) {
    control_rx.close();
    *control_closed = true;
    if let Some(pending) = pending_control.as_mut() {
        pending.apply_restoration(restoration);
        pending.reject_response(message);
    }
    while let Ok(queued) = control_rx.try_recv() {
        let _ = queued
            .response
            .send(Err(ProcessControlError::Worker(message.to_string())));
    }
}

fn duplicate_terminal_payload(kind: &str) -> TaskErrorPayload {
    TaskErrorPayload {
        code: TaskErrorCode::SchemaMismatch,
        message: format!(
            "Backend emitted more than one terminal NDJSON envelope; duplicate `{kind}`."
        ),
        details: None,
    }
}

fn handle_reader_message<R: Runtime>(
    app: &AppHandle<R>,
    message: ReaderMessage,
    terminal: &mut TerminalState,
) -> bool {
    match message {
        ReaderMessage::Stdout(ClassifiedLine::Empty) => false,
        ReaderMessage::Stdout(ClassifiedLine::Progress(payload)) => {
            let _ = app.emit(TaskEventName::TaskProgress.as_str(), payload);
            false
        }
        ReaderMessage::Stdout(ClassifiedLine::ResumeStatus(payload)) => {
            let _ = app.emit(TaskEventName::TaskResumeStatus.as_str(), payload);
            false
        }
        ReaderMessage::Stdout(ClassifiedLine::Log(message)) | ReaderMessage::Stderr(message) => {
            let _ = app.emit(TaskEventName::TaskLog.as_str(), TaskLogPayload { message });
            false
        }
        ReaderMessage::Stdout(ClassifiedLine::Completed(payload)) => {
            terminal.record_completed(payload)
        }
        ReaderMessage::Stdout(ClassifiedLine::Error(payload)) => {
            terminal.record_backend_error(payload)
        }
        ReaderMessage::Stdout(ClassifiedLine::SchemaMismatch(payload)) => {
            terminal.record_supervisor_error(payload);
            true
        }
        ReaderMessage::PipeFailure {
            stream,
            operation,
            message,
        } => {
            terminal.record_supervisor_error(pipe_failure_payload(stream, operation, message));
            true
        }
    }
}

fn spawn_process_control_work<C: ProcessControl + 'static>(
    controller: Arc<C>,
    kind: ProcessControlKind,
    is_paused: bool,
) -> JoinHandle<(Result<(), ProcessControlError>, bool)> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut next_paused = is_paused;
        let result = handle_pause_resume(controller.as_ref(), kind, &mut next_paused);
        (result, next_paused)
    })
}

fn backend_error_payload(
    code: TaskErrorCode,
    message: String,
    stderr_capture: &StderrCapture,
) -> TaskErrorPayload {
    let details = stderr_capture.summary().map(|traceback| {
        serde_json::Map::from_iter([(
            "traceback".to_string(),
            serde_json::Value::String(traceback),
        )])
    });
    TaskErrorPayload {
        code,
        message,
        details,
    }
}

enum ExitDisposition {
    Success,
    Failed(String),
    WaitFailed(String),
}

fn classify_exit(status: io::Result<ExitStatus>) -> ExitDisposition {
    match status {
        Ok(status) if status.success() => ExitDisposition::Success,
        Ok(status) => ExitDisposition::Failed(status.to_string()),
        Err(error) => ExitDisposition::WaitFailed(error.to_string()),
    }
}

fn resolve_non_cancelled_terminal(
    terminal: Option<TerminalEvent>,
    exit: ExitDisposition,
    stderr_capture: &StderrCapture,
) -> TerminalEvent {
    match terminal {
        Some(TerminalEvent::SupervisorError(payload)) => TerminalEvent::SupervisorError(payload),
        Some(TerminalEvent::BackendError(payload)) => TerminalEvent::BackendError(payload),
        Some(TerminalEvent::Completed(payload)) if matches!(exit, ExitDisposition::Success) => {
            TerminalEvent::Completed(payload)
        }
        Some(TerminalEvent::Completed(_)) | None => {
            let payload = match exit {
                ExitDisposition::Success => backend_error_payload(
                    TaskErrorCode::SchemaMismatch,
                    "Backend exited successfully without a terminal NDJSON envelope.".to_string(),
                    stderr_capture,
                ),
                ExitDisposition::Failed(status) => backend_error_payload(
                    TaskErrorCode::RuntimePanic,
                    format!("Backend process exited with status {status}."),
                    stderr_capture,
                ),
                ExitDisposition::WaitFailed(error) => backend_error_payload(
                    TaskErrorCode::ProcessFailed,
                    format!("Failed while waiting for backend process: {error}"),
                    stderr_capture,
                ),
            };
            TerminalEvent::SupervisorError(payload)
        }
    }
}

fn emit_terminal_event<R: Runtime>(
    app: &AppHandle<R>,
    status: io::Result<ExitStatus>,
    terminal: Option<TerminalEvent>,
    cancel_token: &CancellationToken,
    stderr_capture: &StderrCapture,
) {
    if let Some(reason) = cancel_token.reason() {
        let (reason, details) = match reason {
            CancelReason::User => (TaskCancelledReason::User, None),
            CancelReason::Stalled => (
                TaskCancelledReason::Stalled,
                stderr_capture.summary().map(|traceback| {
                    serde_json::Map::from_iter([
                        (
                            "traceback".to_string(),
                            serde_json::Value::String(traceback),
                        ),
                        (
                            "message".to_string(),
                            serde_json::Value::String(
                                "Backend stalled — no progress within the configured timeout."
                                    .to_string(),
                            ),
                        ),
                    ])
                }),
            ),
        };
        let _ = app.emit(
            TaskEventName::TaskCancelled.as_str(),
            TaskCancelledPayload { reason, details },
        );
        return;
    }

    match resolve_non_cancelled_terminal(terminal, classify_exit(status), stderr_capture) {
        TerminalEvent::Completed(payload) => {
            let _ = app.emit(TaskEventName::TaskCompleted.as_str(), payload);
        }
        TerminalEvent::BackendError(payload) | TerminalEvent::SupervisorError(payload) => {
            let _ = app.emit(TaskEventName::TaskError.as_str(), payload);
        }
    }
}

fn handle_pause_resume(
    controller: &dyn ProcessControl,
    kind: ProcessControlKind,
    is_paused: &mut bool,
) -> Result<(), ProcessControlError> {
    match kind {
        ProcessControlKind::Pause if !*is_paused => {
            controller.suspend()?;
            *is_paused = true;
        }
        ProcessControlKind::Resume if *is_paused => {
            controller.resume()?;
            *is_paused = false;
        }
        ProcessControlKind::Pause | ProcessControlKind::Resume => {}
    }
    Ok(())
}

fn parse_stall_timeout() -> Option<Duration> {
    let secs = env::var(STALL_TIMEOUT_ENV)
        .ok()
        .and_then(|value| value.trim().parse::<u64>().ok())
        .unwrap_or(DEFAULT_STALL_TIMEOUT_SECS);
    (secs != 0).then(|| Duration::from_secs(secs))
}

#[cfg(test)]
mod tests {
    use super::*;
    use command_group::AsyncCommandGroup;
    use std::process::Stdio;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Mutex;

    static STALL_TIMEOUT_MUTEX: Mutex<()> = Mutex::new(());

    struct NoopController;

    impl ProcessControl for NoopController {
        fn suspend(&self) -> Result<(), ProcessControlError> {
            Ok(())
        }

        fn resume(&self) -> Result<(), ProcessControlError> {
            Ok(())
        }
    }

    #[test]
    fn parse_stall_timeout_uses_default_when_unset_or_invalid() {
        let _guard = STALL_TIMEOUT_MUTEX.lock().unwrap();
        let stash = env::var(STALL_TIMEOUT_ENV).ok();
        env::remove_var(STALL_TIMEOUT_ENV);
        assert_eq!(
            parse_stall_timeout(),
            Some(Duration::from_secs(DEFAULT_STALL_TIMEOUT_SECS))
        );
        env::set_var(STALL_TIMEOUT_ENV, "invalid");
        assert_eq!(
            parse_stall_timeout(),
            Some(Duration::from_secs(DEFAULT_STALL_TIMEOUT_SECS))
        );
        match stash {
            Some(value) => env::set_var(STALL_TIMEOUT_ENV, value),
            None => env::remove_var(STALL_TIMEOUT_ENV),
        }
    }

    #[test]
    fn parse_stall_timeout_returns_none_for_zero() {
        let _guard = STALL_TIMEOUT_MUTEX.lock().unwrap();
        let stash = env::var(STALL_TIMEOUT_ENV).ok();
        env::set_var(STALL_TIMEOUT_ENV, "0");
        assert_eq!(parse_stall_timeout(), None);
        match stash {
            Some(value) => env::set_var(STALL_TIMEOUT_ENV, value),
            None => env::remove_var(STALL_TIMEOUT_ENV),
        }
    }

    #[test]
    fn pause_and_resume_are_idempotent() {
        let mut paused = false;
        handle_pause_resume(&NoopController, ProcessControlKind::Pause, &mut paused).unwrap();
        handle_pause_resume(&NoopController, ProcessControlKind::Pause, &mut paused).unwrap();
        assert!(paused);
        handle_pause_resume(&NoopController, ProcessControlKind::Resume, &mut paused).unwrap();
        assert!(!paused);
    }

    #[test]
    fn process_control_failure_does_not_change_pause_state() {
        struct FailingController;
        impl ProcessControl for FailingController {
            fn suspend(&self) -> Result<(), ProcessControlError> {
                Err(ProcessControlError::NotFound)
            }
            fn resume(&self) -> Result<(), ProcessControlError> {
                Ok(())
            }
        }

        let mut paused = false;
        let result =
            handle_pause_resume(&FailingController, ProcessControlKind::Pause, &mut paused);
        assert!(matches!(result, Err(ProcessControlError::NotFound)));
        assert!(!paused);
    }

    fn completed_payload() -> TaskCompletedPayload {
        TaskCompletedPayload {
            output_path: "D:/out.mp4".to_string(),
            processed_frames: 10,
            time_seconds: 1.0,
        }
    }

    fn task_error(code: TaskErrorCode, message: &str) -> TaskErrorPayload {
        TaskErrorPayload {
            code,
            message: message.to_string(),
            details: None,
        }
    }

    #[test]
    fn duplicate_terminal_overrides_an_earlier_completed_envelope() {
        let mut terminal = TerminalState::default();
        assert!(!terminal.record_completed(completed_payload()));
        assert!(
            terminal.record_completed(completed_payload()),
            "a duplicate terminal envelope is a fatal protocol violation"
        );

        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
            }
            _ => panic!("protocol failure must override completed"),
        }
    }

    #[test]
    fn schema_mismatch_after_completed_overrides_the_completed_envelope() {
        let mut terminal = TerminalState::default();
        assert!(!terminal.record_completed(completed_payload()));
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::SchemaMismatch,
            "invalid NDJSON envelope",
        ));

        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
                assert_eq!(payload.message, "invalid NDJSON envelope");
            }
            _ => panic!("schema mismatch must override completed"),
        }
    }

    #[test]
    fn reader_drain_failure_overrides_completed() {
        let mut terminal = TerminalState::default();
        assert!(!terminal.record_completed(completed_payload()));
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::ProcessFailed,
            "reader drain failed",
        ));

        match resolve_non_cancelled_terminal(
            terminal.take(),
            ExitDisposition::Success,
            &StderrCapture::new(),
        ) {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
                assert_eq!(payload.message, "reader drain failed");
            }
            _ => panic!("reader failure must override completed"),
        }
    }

    #[test]
    fn nonzero_exit_invalidates_a_completed_envelope() {
        let mut terminal = TerminalState::default();
        assert!(!terminal.record_completed(completed_payload()));

        match resolve_non_cancelled_terminal(
            terminal.take(),
            ExitDisposition::Failed("exit code: 7".to_string()),
            &StderrCapture::new(),
        ) {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::RuntimePanic));
                assert!(payload.message.contains("exit code: 7"));
            }
            _ => panic!("nonzero exit must invalidate completed"),
        }
    }

    #[test]
    fn successful_exit_without_terminal_envelope_is_schema_mismatch() {
        match resolve_non_cancelled_terminal(None, ExitDisposition::Success, &StderrCapture::new())
        {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
                assert!(payload
                    .message
                    .contains("without a terminal NDJSON envelope"));
            }
            _ => panic!("missing terminal envelope must fail"),
        }
    }

    #[test]
    fn failed_exit_without_terminal_envelope_is_runtime_panic() {
        let capture = StderrCapture::new();
        capture.record("RuntimeError: decoder crashed");

        match resolve_non_cancelled_terminal(
            None,
            ExitDisposition::Failed("exit code: 9".to_string()),
            &capture,
        ) {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::RuntimePanic));
                assert!(payload.message.contains("exit code: 9"));
                assert_eq!(
                    payload.details.expect("stderr details")["traceback"],
                    "RuntimeError: decoder crashed"
                );
            }
            _ => panic!("failed process must surface as runtime panic"),
        }
    }

    #[test]
    fn wait_failure_without_terminal_envelope_is_process_failed() {
        match resolve_non_cancelled_terminal(
            None,
            ExitDisposition::WaitFailed("wait handle closed".to_string()),
            &StderrCapture::new(),
        ) {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
                assert!(payload.message.contains("wait handle closed"));
            }
            _ => panic!("wait failure must surface as process failure"),
        }
    }

    #[test]
    fn successful_exit_preserves_a_completed_envelope() {
        let completed = completed_payload();
        match resolve_non_cancelled_terminal(
            Some(TerminalEvent::Completed(completed)),
            ExitDisposition::Success,
            &StderrCapture::new(),
        ) {
            TerminalEvent::Completed(payload) => {
                assert_eq!(payload.output_path, "D:/out.mp4");
                assert_eq!(payload.processed_frames, 10);
            }
            _ => panic!("completed envelope should be committed"),
        }
    }

    #[test]
    fn wait_failure_invalidates_a_completed_envelope() {
        match resolve_non_cancelled_terminal(
            Some(TerminalEvent::Completed(completed_payload())),
            ExitDisposition::WaitFailed("lost child handle".to_string()),
            &StderrCapture::new(),
        ) {
            TerminalEvent::SupervisorError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
                assert!(payload.message.contains("lost child handle"));
            }
            _ => panic!("wait failure must override completion"),
        }
    }

    #[test]
    fn backend_error_envelope_has_priority_over_exit_status() {
        let backend = task_error(TaskErrorCode::MissingModel, "weights unavailable");
        match resolve_non_cancelled_terminal(
            Some(TerminalEvent::BackendError(backend)),
            ExitDisposition::Failed("exit code: 2".to_string()),
            &StderrCapture::new(),
        ) {
            TerminalEvent::BackendError(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::MissingModel));
                assert_eq!(payload.message, "weights unavailable");
            }
            _ => panic!("typed backend error must retain precedence"),
        }
    }

    #[test]
    fn first_supervisor_error_is_sticky_during_shutdown() {
        let mut terminal = TerminalState::default();
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::SchemaMismatch,
            "first protocol failure",
        ));
        terminal.record_supervisor_error(task_error(
            TaskErrorCode::ProcessFailed,
            "later pipe failure",
        ));

        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
                assert_eq!(payload.message, "first protocol failure");
            }
            _ => panic!("first supervisor failure must remain authoritative"),
        }
    }

    #[test]
    fn duplicate_backend_error_becomes_a_protocol_failure() {
        let mut terminal = TerminalState::default();
        assert!(
            !terminal.record_backend_error(task_error(TaskErrorCode::MissingModel, "first error",))
        );
        assert!(
            terminal.record_backend_error(task_error(TaskErrorCode::RuntimePanic, "second error",))
        );

        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
                assert!(payload.message.contains("duplicate `error`"));
            }
            _ => panic!("duplicate backend errors must be fatal"),
        }
    }

    struct BlockingController {
        started: Arc<AtomicBool>,
    }

    impl ProcessControl for BlockingController {
        fn suspend(&self) -> Result<(), ProcessControlError> {
            self.started.store(true, Ordering::Release);
            std::thread::sleep(Duration::from_millis(250));
            Ok(())
        }

        fn resume(&self) -> Result<(), ProcessControlError> {
            Ok(())
        }
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn blocking_process_control_does_not_block_cancellation_observation() {
        let started = Arc::new(AtomicBool::new(false));
        let controller = Arc::new(BlockingController {
            started: Arc::clone(&started),
        });
        let cancel_token = CancellationToken::new();
        let mut control = spawn_process_control_work(controller, ProcessControlKind::Pause, false);
        let cancel = cancel_token.clone();
        let trigger = tokio::spawn(async move {
            while !started.load(Ordering::Acquire) {
                tokio::task::yield_now().await;
            }
            cancel.cancel(CancelReason::User);
        });

        let cancellation_won = tokio::time::timeout(Duration::from_millis(100), async {
            tokio::select! {
                _ = cancel_token.cancelled() => true,
                _ = &mut control => false,
            }
        })
        .await
        .expect("supervisor select must remain responsive");
        trigger.await.expect("trigger");
        assert!(cancellation_won);
        let _ = control.await.expect("blocking control worker");
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn timed_out_pause_is_owned_and_compensated_after_late_success() {
        let started = Arc::new(AtomicBool::new(false));
        let controller = Arc::new(BlockingController {
            started: Arc::clone(&started),
        });
        let (response_tx, response_rx) = oneshot::channel();
        let mut pending_control = Some(PendingControl::new(
            Arc::clone(&controller),
            ProcessControlKind::Pause,
            false,
            response_tx,
            Duration::from_millis(10),
        ));

        assert!(matches!(
            wait_for_pending_control(&mut pending_control).await,
            PendingControlEvent::TimedOut
        ));
        pending_control
            .as_mut()
            .expect("pending control")
            .timeout_response();

        let response = response_rx.await.expect("timeout response");
        assert!(matches!(response, Err(ProcessControlError::Worker(_))));
        assert!(
            pending_control.is_some(),
            "timeout must not detach the worker"
        );

        let PendingControlEvent::Finished(joined) =
            wait_for_pending_control(&mut pending_control).await
        else {
            panic!("timed-out worker must eventually finish");
        };
        let pending = pending_control.take().expect("pending control");
        let (result, next_paused) = joined.expect("blocking worker join");
        assert_eq!(pending.compensation_target(next_paused), Some(false));
        result.expect("late control result");
        assert!(next_paused);

        let mut compensation = PendingControl::compensation(controller, next_paused, false);
        let PendingControlEvent::Finished(joined) = compensation.wait().await else {
            panic!("compensation must finish before its deadline");
        };
        let (result, restored_paused) = joined.expect("compensation join");
        result.expect("resume compensation");
        assert!(!restored_paused);
        assert!(started.load(Ordering::Acquire));
    }

    async fn finish_after_terminal_rejection<C: ProcessControl + 'static>(
        controller: Arc<C>,
        kind: ProcessControlKind,
        initial_paused: bool,
    ) -> (PendingControl, Result<(), ProcessControlError>, bool) {
        let (response_tx, response_rx) = oneshot::channel();
        let mut pending = PendingControl::new(
            controller,
            kind,
            initial_paused,
            response_tx,
            Duration::from_secs(1),
        );
        pending.apply_restoration(ControlRestoration::Target(false));
        pending.reject_response("terminal result received");
        assert!(matches!(
            response_rx.await.expect("terminal rejection"),
            Err(ProcessControlError::Worker(_))
        ));
        let PendingControlEvent::Finished(joined) = pending.wait().await else {
            panic!("process-control worker must finish");
        };
        let (result, next_paused) = joined.expect("process-control worker join");
        (pending, result, next_paused)
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn terminal_rejection_marks_an_in_flight_pause_for_compensation() {
        let started = Arc::new(AtomicBool::new(false));
        let controller = Arc::new(BlockingController {
            started: Arc::clone(&started),
        });
        let (pending, result, next_paused) =
            finish_after_terminal_rejection(controller, ProcessControlKind::Pause, false).await;
        result.expect("late pause result");
        assert_eq!(pending.compensation_target(next_paused), Some(false));
    }

    #[tokio::test]
    async fn terminal_rejection_never_repauses_a_successful_in_flight_resume() {
        let (pending, result, next_paused) = finish_after_terminal_rejection(
            Arc::new(NoopController),
            ProcessControlKind::Resume,
            true,
        )
        .await;
        result.expect("late resume result");
        assert!(!next_paused);
        assert_eq!(pending.compensation_target(next_paused), None);
    }

    #[tokio::test]
    async fn closing_control_channel_rejects_buffered_work() {
        let (control_tx, mut control_rx) = mpsc::channel(2);
        let (first_tx, first_rx) = oneshot::channel();
        let (second_tx, second_rx) = oneshot::channel();
        control_tx
            .send(TaskControlMessage {
                kind: ProcessControlKind::Pause,
                response: first_tx,
            })
            .await
            .expect("queue first control");
        control_tx
            .send(TaskControlMessage {
                kind: ProcessControlKind::Resume,
                response: second_tx,
            })
            .await
            .expect("queue second control");
        let mut control_closed = false;
        let mut pending_control = None;

        close_control_channel(
            &mut control_rx,
            &mut control_closed,
            &mut pending_control,
            "task is stopping",
            ControlRestoration::Abandon,
        );

        assert!(control_closed);
        for response in [first_rx.await, second_rx.await] {
            assert!(matches!(
                response.expect("rejection response"),
                Err(ProcessControlError::Worker(_))
            ));
        }
        let (late_tx, _late_rx) = oneshot::channel();
        assert!(control_tx
            .send(TaskControlMessage {
                kind: ProcessControlKind::Pause,
                response: late_tx,
            })
            .await
            .is_err());
    }

    #[cfg(target_os = "windows")]
    fn sleeping_process_group() -> AsyncGroupChild {
        let mut command = tokio::process::Command::new("cmd");
        command
            .args(["/C", "ping -n 30 127.0.0.1 >NUL"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command
            .group()
            .kill_on_drop(true)
            .spawn()
            .expect("spawn sleeping process group")
    }

    #[cfg(not(target_os = "windows"))]
    fn sleeping_process_group() -> AsyncGroupChild {
        let mut command = tokio::process::Command::new("sh");
        command
            .args(["-c", "sleep 30"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command
            .group()
            .kill_on_drop(true)
            .spawn()
            .expect("spawn sleeping process group")
    }

    #[tokio::test]
    async fn requested_process_group_kill_is_observed_and_reaped() {
        let mut child = SupervisedChild::new(sleeping_process_group());
        let mut kill_deadline = None;
        let mut terminal = TerminalState::default();
        let mut pending_control = None;
        let (_control_tx, mut control_rx) = mpsc::channel(1);
        let mut control_closed = false;
        request_kill(
            &mut child,
            &mut kill_deadline,
            &mut terminal,
            &mut pending_control,
            &mut control_rx,
            &mut control_closed,
        );

        assert!(control_closed);
        let status = tokio::time::timeout(Duration::from_secs(2), async {
            loop {
                if let Some(status) = child.try_wait().expect("poll child") {
                    return status;
                }
                tokio::time::sleep(Duration::from_millis(20)).await;
            }
        })
        .await
        .expect("killed group must be reaped");
        assert!(!status.success());
    }
}
