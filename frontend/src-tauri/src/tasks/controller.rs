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

use tokio::sync::{mpsc, oneshot};
use tokio::task::JoinHandle;

use crate::generated::{BackendProcessSpec, StartTaskSpec};
use crate::models::{
    TaskCancelledPayload, TaskCancelledReason, TaskCompletedPayload, TaskErrorCode,
    TaskErrorPayload, TaskLogPayload,
};
use crate::process_control::{ProcessControl, ProcessControlError};
use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::cleanup::{own_late_cleanup, PendingControlCleanup};
use crate::tasks::envelope::ClassifiedLine;
use crate::tasks::ports::{TaskDomainEvent, TaskEventSink, TaskLifecyclePort};
use crate::tasks::readers::{pipe_failure_payload, ProgressBeat, ReaderMessage};
use crate::tasks::state::StartLease;
use crate::tasks::stderr::StderrCapture;
use crate::tasks::subprocess::{ProcessGroupChild, ProcessGroupOwner, ReapOutcome, ReapTicket};
#[cfg(test)]
use crate::tasks::TaskState;
use crate::tasks::{ProcessControlKind, TaskControlMessage};

const DEFAULT_STALL_TIMEOUT_SECS: u64 = 600;
const DEFAULT_WATCHDOG_POLL_INTERVAL_SECS: u64 = 5;
const PIPE_DRAIN_TIMEOUT: Duration = Duration::from_secs(5);
// Leave one second for the controller result to traverse the oneshot before
// the IPC-side five-second response deadline expires.
const PROCESS_CONTROL_TIMEOUT: Duration = Duration::from_secs(4);
const TERMINAL_EXIT_GRACE: Duration = Duration::from_secs(5);
const CHILD_EXIT_POLL_INTERVAL: Duration = Duration::from_millis(50);
const STALL_TIMEOUT_ENV: &str = "VP_TASK_STALL_TIMEOUT_SECS";

pub(super) struct SupervisorDependencies {
    event_sink: Arc<dyn TaskEventSink>,
    lifecycle: Arc<dyn TaskLifecyclePort>,
    process_controller: Arc<dyn ProcessControl>,
}

impl SupervisorDependencies {
    pub(super) fn new(
        event_sink: Arc<dyn TaskEventSink>,
        lifecycle: Arc<dyn TaskLifecyclePort>,
        process_controller: Arc<dyn ProcessControl>,
    ) -> Self {
        Self {
            event_sink,
            lifecycle,
            process_controller,
        }
    }
}

pub(super) struct SupervisorIo {
    control_rx: mpsc::Receiver<TaskControlMessage>,
    output_rx: mpsc::Receiver<ReaderMessage>,
    stdin_writer: JoinHandle<()>,
    stdout_reader: JoinHandle<()>,
    stderr_reader: JoinHandle<()>,
    stderr_capture: StderrCapture,
}

impl SupervisorIo {
    pub(super) fn new(
        control_rx: mpsc::Receiver<TaskControlMessage>,
        output_rx: mpsc::Receiver<ReaderMessage>,
        stdin_writer: JoinHandle<()>,
        stdout_reader: JoinHandle<()>,
        stderr_reader: JoinHandle<()>,
        stderr_capture: StderrCapture,
    ) -> Self {
        Self {
            control_rx,
            output_rx,
            stdin_writer,
            stdout_reader,
            stderr_reader,
            stderr_capture,
        }
    }
}

struct SupervisedProcess {
    child: ProcessGroupOwner,
    reap_ticket: ReapTicket,
}

struct TaskSupervisorSession {
    dependencies: SupervisorDependencies,
    process: SupervisedProcess,
    lease: StartLease,
    io: SupervisorIo,
    cancel_token: CancellationToken,
    progress_beat: ProgressBeat,
    control_cleanup: PendingControlCleanup,
}

struct SupervisorRecoveryContext {
    event_sink: Arc<dyn TaskEventSink>,
    lifecycle: Arc<dyn TaskLifecyclePort>,
    lease: StartLease,
    stderr_capture: StderrCapture,
    reap_ticket: ReapTicket,
    control_cleanup: PendingControlCleanup,
}

impl TaskSupervisorSession {
    fn new(
        child: ProcessGroupChild,
        lease: StartLease,
        dependencies: SupervisorDependencies,
        io: SupervisorIo,
        progress_beat: ProgressBeat,
    ) -> (Self, SupervisorRecoveryContext) {
        let cancel_token = lease.cancellation_token();
        let (child, reap_ticket) =
            ProcessGroupOwner::new(child, "supervised backend process group");
        let control_cleanup = PendingControlCleanup::default();
        let recovery = SupervisorRecoveryContext {
            event_sink: Arc::clone(&dependencies.event_sink),
            lifecycle: Arc::clone(&dependencies.lifecycle),
            lease: lease.clone(),
            stderr_capture: io.stderr_capture.clone(),
            reap_ticket: reap_ticket.clone(),
            control_cleanup: control_cleanup.clone(),
        };
        (
            Self {
                dependencies,
                process: SupervisedProcess { child, reap_ticket },
                lease,
                io,
                cancel_token,
                progress_beat,
                control_cleanup,
            },
            recovery,
        )
    }
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
    type Output = Result<T, tokio::task::JoinError>;

    fn poll(mut self: Pin<&mut Self>, context: &mut Context<'_>) -> Poll<Self::Output> {
        Pin::new(&mut self.handle).poll(context)
    }
}

impl<T> Drop for AbortOnDropTask<T> {
    fn drop(&mut self) {
        self.handle.abort();
    }
}

struct PendingControl {
    work: PendingControlCleanup,
    deadline: Pin<Box<tokio::time::Sleep>>,
    timeout: Duration,
    response: Option<oneshot::Sender<Result<(), ProcessControlError>>>,
    initial_paused: bool,
    shutdown: ShutdownDirective,
    phase: ControlPhase,
}

#[derive(Clone, Copy)]
enum ControlRestoration {
    Target(bool),
    Abandon,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ShutdownDirective {
    Undecided,
    RestoreTo(bool),
    Abandon,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ControlPhase {
    Requested,
    Compensation,
}

enum PendingControlEvent {
    Finished(Result<(Result<(), ProcessControlError>, bool), tokio::task::JoinError>),
    TimedOut,
}

impl PendingControl {
    fn new(
        controller: Arc<dyn ProcessControl>,
        kind: ProcessControlKind,
        is_paused: bool,
        response: oneshot::Sender<Result<(), ProcessControlError>>,
        timeout: Duration,
        work: PendingControlCleanup,
    ) -> Self {
        work.start(|| spawn_process_control_work(controller, kind, is_paused));
        Self {
            work,
            deadline: Box::pin(tokio::time::sleep(timeout)),
            timeout,
            response: Some(response),
            initial_paused: is_paused,
            shutdown: ShutdownDirective::Undecided,
            phase: ControlPhase::Requested,
        }
    }

    fn reject_response(&mut self, message: &str) {
        if let Some(response) = self.response.take() {
            let _ = response.send(Err(ProcessControlError::Worker(message.to_string())));
        }
    }

    fn compensation(
        controller: Arc<dyn ProcessControl>,
        current_paused: bool,
        target_paused: bool,
        work: PendingControlCleanup,
    ) -> Self {
        let kind = if target_paused {
            ProcessControlKind::Pause
        } else {
            ProcessControlKind::Resume
        };
        work.start(|| spawn_process_control_work(controller, kind, current_paused));
        Self {
            work,
            deadline: Box::pin(tokio::time::sleep(PROCESS_CONTROL_TIMEOUT)),
            timeout: PROCESS_CONTROL_TIMEOUT,
            response: None,
            initial_paused: target_paused,
            shutdown: ShutdownDirective::Undecided,
            phase: ControlPhase::Compensation,
        }
    }

    fn apply_restoration(&mut self, restoration: ControlRestoration) {
        if self.shutdown == ShutdownDirective::Abandon {
            return;
        }
        self.shutdown = match restoration {
            ControlRestoration::Target(target) => ShutdownDirective::RestoreTo(target),
            ControlRestoration::Abandon => ShutdownDirective::Abandon,
        };
    }

    fn compensation_target(&self, next_paused: bool) -> Option<bool> {
        match self.shutdown {
            ShutdownDirective::RestoreTo(target) if next_paused != target => Some(target),
            _ => None,
        }
    }

    fn into_abandoned_work(mut self, message: &str) -> PendingControlCleanup {
        self.apply_restoration(ControlRestoration::Abandon);
        self.reject_response(message);
        self.work
    }

    fn into_timed_out_work(mut self) -> PendingControlCleanup {
        self.apply_restoration(ControlRestoration::Abandon);
        self.reject_response(&format!(
            "operation timed out after {} seconds",
            self.timeout.as_secs_f64()
        ));
        self.work
    }

    async fn wait(&mut self) -> PendingControlEvent {
        tokio::select! {
            result = self.work.wait() => PendingControlEvent::Finished(result.unwrap_or_else(|| {
                Ok((
                    Err(ProcessControlError::Worker(
                        "process-control worker ownership was lost".to_string(),
                    )),
                    self.initial_paused,
                ))
            })),
            _ = self.deadline.as_mut() => PendingControlEvent::TimedOut,
        }
    }
}

pub(super) fn spawn_task_supervisor(
    child: ProcessGroupChild,
    lease: StartLease,
    dependencies: SupervisorDependencies,
    io: SupervisorIo,
    progress_beat: ProgressBeat,
) {
    let (session, recovery) =
        TaskSupervisorSession::new(child, lease, dependencies, io, progress_beat);
    let supervisor = tokio::spawn(run_task_supervisor(session));
    tokio::spawn(monitor_supervisor(supervisor, move |message| async move {
        recover_supervisor_join_failure(recovery, message).await;
    }));
}

async fn monitor_supervisor<T, F, Fut>(supervisor: JoinHandle<T>, on_join_failure: F)
where
    F: FnOnce(String) -> Fut,
    Fut: Future<Output = ()>,
{
    if let Err(error) = supervisor.await {
        on_join_failure(error.to_string()).await;
    }
}

async fn recover_supervisor_join_failure(recovery: SupervisorRecoveryContext, message: String) {
    let SupervisorRecoveryContext {
        event_sink,
        lifecycle,
        lease,
        stderr_capture,
        mut reap_ticket,
        control_cleanup,
    } = recovery;
    // `run_task_supervisor` owns `ProcessGroupOwner` and every pipe/control task. A panic first
    // unwinds those structured owners: the child guard terminates the process group and the
    // reader guards abort their tasks. Only then does this monitor receive the JoinError and
    // atomically publish the one permitted terminal event while releasing the task slot.
    let mut payload = supervisor_join_failure_payload(&message, &stderr_capture);
    if !lifecycle.begin_reaping(&lease).await {
        eprintln!("supervisor panic cleanup no longer owns its task lease");
        return;
    }
    let late_control = if control_cleanup.has_work() {
        match tokio::time::timeout(PROCESS_CONTROL_TIMEOUT, control_cleanup.wait()).await {
            Err(_) => Some(control_cleanup),
            Ok(Some(Ok((Ok(()), _)))) => None,
            Ok(Some(Ok((Err(error), _)))) => {
                payload.message = format!(
                    "{} Process-control cleanup completed with an error: {error}",
                    payload.message
                );
                None
            }
            Ok(Some(Err(error))) => {
                payload.message = format!(
                    "{} Process-control cleanup worker failed: {error}",
                    payload.message
                );
                None
            }
            Ok(None) => {
                payload.message = format!(
                    "{} Process-control cleanup lost worker ownership.",
                    payload.message
                );
                None
            }
        }
    } else {
        None
    };
    let reap_outcome = reap_ticket
        .wait_bounded(StartTaskSpec::TERMINATION_TIMEOUT)
        .await;
    if reap_outcome == Some(ReapOutcome::Reaped) && late_control.is_none() {
        if !lifecycle
            .finish_once(
                &lease,
                Box::new(move || {
                    if let Err(error) = event_sink.emit(TaskDomainEvent::Error(payload)) {
                        eprintln!("unable to emit supervisor failure: {error}");
                    }
                }),
            )
            .await
        {
            eprintln!("supervisor panic completion no longer owns its task lease");
        }
        return;
    }

    let reap_timed_out = reap_outcome.is_none();
    let details = match reap_outcome.as_ref() {
        Some(ReapOutcome::Failed(error)) => error.clone(),
        None => "timed out while waiting for panic cleanup to reap the backend".to_string(),
        Some(ReapOutcome::Reaped) => {
            "timed out while waiting for the panic cleanup process-control worker".to_string()
        }
    };
    let cleanup_sink = Arc::clone(&event_sink);
    if !lifecycle
        .fail_cleanup_once(
            &lease,
            Box::new(move || {
                payload.message = format!("{} Cleanup remains blocked: {details}", payload.message);
                if let Err(error) = cleanup_sink.emit(TaskDomainEvent::Error(payload)) {
                    eprintln!("unable to emit supervisor cleanup failure: {error}");
                }
            }),
        )
        .await
    {
        eprintln!("supervisor panic cleanup no longer owns its task lease");
    }
    if reap_timed_out || late_control.is_some() {
        own_late_cleanup(lifecycle, lease, reap_ticket, late_control).await;
    }
}

fn supervisor_join_failure_payload(
    message: &str,
    stderr_capture: &StderrCapture,
) -> TaskErrorPayload {
    backend_error_payload(
        TaskErrorCode::ProcessFailed,
        format!("Task supervisor terminated unexpectedly: {message}"),
        stderr_capture,
    )
}

async fn run_task_supervisor(session: TaskSupervisorSession) {
    let TaskSupervisorSession {
        dependencies:
            SupervisorDependencies {
                event_sink,
                lifecycle,
                process_controller,
            },
        process: SupervisedProcess {
            mut child,
            reap_ticket,
        },
        lease,
        io:
            SupervisorIo {
                mut control_rx,
                mut output_rx,
                stdin_writer,
                stdout_reader,
                stderr_reader,
                stderr_capture,
            },
        cancel_token,
        progress_beat,
        control_cleanup,
    } = session;
    let mut stdin_writer = AbortOnDropTask::new(stdin_writer);
    let mut stdout_reader = AbortOnDropTask::new(stdout_reader);
    let mut stderr_reader = AbortOnDropTask::new(stderr_reader);

    let mut kill_deadline = None;
    let mut exit_status = None;
    let mut reap_confirmed = false;
    let mut output_closed = false;
    let mut control_closed = false;
    let mut is_paused = false;
    let mut terminal = TerminalState::default();
    let mut terminal_deadline = None;
    let mut pending_control: Option<PendingControl> = None;
    let mut cleanup_control_work: Option<PendingControlCleanup> = None;
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
                        let protocol_fatal = handle_reader_message(event_sink.as_ref(), message, &mut terminal);
                        if !had_terminal && terminal.has_event() {
                            if !lifecycle.seal_owned(&lease).await
                                && !cancel_token.is_cancelled()
                            {
                                terminal.record_supervisor_error(TaskErrorPayload {
                                    code: TaskErrorCode::ProcessFailed,
                                    message: "Task lifecycle ownership was lost while sealing a terminal result."
                                        .to_string(),
                                    details: None,
                                });
                            }
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
                                control_cleanup.clone(),
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
                        if let Err(ProcessControlError::StateUnknown(message)) = &result {
                            pending.apply_restoration(ControlRestoration::Abandon);
                            terminal.record_supervisor_error(TaskErrorPayload {
                                code: TaskErrorCode::ProcessFailed,
                                message: format!(
                                    "Process control left the operating-system state unknown: {message}"
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
                        } else if pending.phase == ControlPhase::Compensation && result.is_err() {
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
                                control_cleanup.clone(),
                            ));
                        } else if result.is_ok() {
                            is_paused = next_paused;
                        }
                        if let Some(response) = pending.response.take() {
                            let _ = response.send(result);
                        }
                    }
                    PendingControlEvent::TimedOut => {
                        let pending = pending_control.take().expect("guarded pending control");
                        cleanup_control_work = Some(pending.into_timed_out_work());
                        terminal.record_supervisor_error(TaskErrorPayload {
                            code: TaskErrorCode::ProcessFailed,
                            message: "Process control timed out; the backend state is unknown and the task was terminated.".to_string(),
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
                        reap_confirmed = true;
                        if !lifecycle.seal_owned(&lease).await
                            && !cancel_token.is_cancelled()
                        {
                            terminal.record_supervisor_error(TaskErrorPayload {
                                code: TaskErrorCode::ProcessFailed,
                                message: "Task lifecycle ownership was lost after backend exit."
                                    .to_string(),
                                details: None,
                            });
                        }
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
                        if !lifecycle.seal_owned(&lease).await
                            && !cancel_token.is_cancelled()
                        {
                            terminal.record_supervisor_error(TaskErrorPayload {
                                code: TaskErrorCode::ProcessFailed,
                                message: "Task lifecycle ownership was lost after backend status polling failed."
                                    .to_string(),
                                details: None,
                            });
                        }
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
                        && lifecycle.cancel_owned(&lease, CancelReason::Stalled).await
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
                    Ok(Some(status)) => {
                        reap_confirmed = true;
                        exit_status = Some(Ok(status));
                    }
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

    if !lifecycle.begin_reaping(&lease).await {
        terminal.record_supervisor_error(TaskErrorPayload {
            code: TaskErrorCode::ProcessFailed,
            message: "Task lifecycle ownership was lost before process reaping completed."
                .to_string(),
            details: None,
        });
    }
    // On a synthetic kill timeout, dropping the owner transfers the stable
    // process-group/job handle to the ticketed reaper. The task slot remains
    // closed until that ticket confirms exit.
    drop(child);

    // A blocking OS control call cannot be aborted safely. Retain its join handle and bound the
    // supervisor wait; if it outlives the deadline, the cleanup coordinator owns it and keeps the
    // single-task slot closed until both the worker and process reaper have finished.
    if let Some(pending) = pending_control.take() {
        let work = pending
            .into_abandoned_work("process control was cancelled because the backend stopped");
        match tokio::time::timeout(PROCESS_CONTROL_TIMEOUT, work.wait()).await {
            Err(_) => cleanup_control_work = Some(work),
            Ok(Some(Ok((Ok(()), _)))) => {}
            Ok(Some(Ok((Err(error), _)))) => {
                terminal.record_supervisor_error(TaskErrorPayload {
                    code: TaskErrorCode::ProcessFailed,
                    message: format!("Process-control cleanup completed with an error: {error}"),
                    details: None,
                });
            }
            Ok(Some(Err(error))) => {
                terminal.record_supervisor_error(TaskErrorPayload {
                    code: TaskErrorCode::ProcessFailed,
                    message: format!("Process-control cleanup worker failed: {error}"),
                    details: None,
                });
            }
            Ok(None) => {
                terminal.record_supervisor_error(TaskErrorPayload {
                    code: TaskErrorCode::ProcessFailed,
                    message: "Process-control cleanup lost worker ownership.".to_string(),
                    details: None,
                });
            }
        }
    }

    if !output_closed {
        let drain_result = tokio::time::timeout(PIPE_DRAIN_TIMEOUT, async {
            while let Some(message) = output_rx.recv().await {
                let _ = handle_reader_message(event_sink.as_ref(), message, &mut terminal);
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
    if reap_confirmed && cleanup_control_work.is_none() {
        let terminal_sink = Arc::clone(&event_sink);
        if !lifecycle
            .finish_once(
                &lease,
                Box::new(move || {
                    if let Err(error) = emit_terminal_event(
                        terminal_sink.as_ref(),
                        status,
                        terminal.take(),
                        &cancel_token,
                        &stderr_capture,
                    ) {
                        eprintln!("unable to emit terminal task event: {error}");
                    }
                }),
            )
            .await
        {
            eprintln!("task completion no longer owns its lifecycle lease");
        }
    } else {
        let cleanup_message = if cleanup_control_work.is_some() {
            "Backend cleanup is waiting for a process-control worker with unknown OS state; new tasks are blocked until cleanup completes."
        } else {
            "Backend cleanup could not confirm that the process group exited; new tasks are blocked until cleanup completes."
        };
        let cleanup_sink = Arc::clone(&event_sink);
        if !lifecycle
            .fail_cleanup_once(
                &lease,
                Box::new(move || {
                    let payload = TaskErrorPayload {
                        code: TaskErrorCode::ProcessFailed,
                        message: cleanup_message.to_string(),
                        details: None,
                    };
                    if let Err(error) = cleanup_sink.emit(TaskDomainEvent::Error(payload)) {
                        eprintln!("unable to emit cleanup failure: {error}");
                    }
                }),
            )
            .await
        {
            eprintln!("task cleanup failure no longer owns its lifecycle lease");
        }
        own_late_cleanup(lifecycle, lease, reap_ticket, cleanup_control_work).await;
    }
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
    child: &mut ProcessGroupOwner,
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
    *kill_deadline = Some(Box::pin(tokio::time::sleep(
        StartTaskSpec::TERMINATION_TIMEOUT,
    )));
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

fn handle_reader_message(
    event_sink: &dyn TaskEventSink,
    message: ReaderMessage,
    terminal: &mut TerminalState,
) -> bool {
    match message {
        ReaderMessage::Stdout(ClassifiedLine::Empty) => false,
        ReaderMessage::Stdout(ClassifiedLine::Progress(payload)) => {
            emit_observation(event_sink, TaskDomainEvent::Progress(payload), terminal)
        }
        ReaderMessage::Stdout(ClassifiedLine::ResumeStatus(payload)) => {
            emit_observation(event_sink, TaskDomainEvent::ResumeStatus(payload), terminal)
        }
        ReaderMessage::Stdout(ClassifiedLine::Log(message)) | ReaderMessage::Stderr(message) => {
            emit_observation(
                event_sink,
                TaskDomainEvent::Log(TaskLogPayload { message }),
                terminal,
            )
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

fn emit_observation(
    event_sink: &dyn TaskEventSink,
    event: TaskDomainEvent,
    terminal: &mut TerminalState,
) -> bool {
    if let Err(error) = event_sink.emit(event) {
        terminal.record_supervisor_error(TaskErrorPayload {
            code: TaskErrorCode::ProcessFailed,
            message: format!("Unable to emit task event: {error}"),
            details: None,
        });
        true
    } else {
        false
    }
}

fn spawn_process_control_work(
    controller: Arc<dyn ProcessControl>,
    kind: ProcessControlKind,
    is_paused: bool,
) -> JoinHandle<(Result<(), ProcessControlError>, bool)> {
    tokio::task::spawn_blocking(move || {
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

fn emit_terminal_event(
    event_sink: &dyn TaskEventSink,
    status: io::Result<ExitStatus>,
    terminal: Option<TerminalEvent>,
    cancel_token: &CancellationToken,
    stderr_capture: &StderrCapture,
) -> Result<(), String> {
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
        return event_sink.emit(TaskDomainEvent::Cancelled(TaskCancelledPayload {
            reason,
            details,
        }));
    }

    match resolve_non_cancelled_terminal(terminal, classify_exit(status), stderr_capture) {
        TerminalEvent::Completed(payload) => event_sink.emit(TaskDomainEvent::Completed(payload)),
        TerminalEvent::BackendError(payload) | TerminalEvent::SupervisorError(payload) => {
            event_sink.emit(TaskDomainEvent::Error(payload))
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
    use std::process::Stdio;
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::Mutex;

    use crate::tasks::test_support::assert_process_exited;

    static STALL_TIMEOUT_MUTEX: Mutex<()> = Mutex::new(());

    async fn wait_for_started(started: &AtomicBool, context: &'static str) {
        tokio::time::timeout(Duration::from_secs(2), async {
            while !started.load(Ordering::Acquire) {
                tokio::task::yield_now().await;
            }
        })
        .await
        .expect(context);
    }

    async fn active_task_fixture() -> (
        Arc<TaskState>,
        StartLease,
        mpsc::Receiver<TaskControlMessage>,
    ) {
        let state = Arc::new(TaskState::default());
        let lease = state.reserve_start().await.expect("reserve task slot");
        let (control_tx, control_rx) = mpsc::channel(1);
        state
            .activate(&lease, control_tx)
            .await
            .expect("activate task slot");
        (state, lease, control_rx)
    }

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

    #[test]
    fn supervisor_join_failure_is_a_typed_process_error_with_stderr_context() {
        let stderr = StderrCapture::new();
        stderr.record("panic in supervisor worker");

        let payload = supervisor_join_failure_payload("task 17 panicked", &stderr);

        assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
        assert!(payload.message.contains("task 17 panicked"));
        assert_eq!(
            payload
                .details
                .as_ref()
                .and_then(|details| details.get("traceback"))
                .and_then(serde_json::Value::as_str),
            Some("panic in supervisor worker")
        );
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn supervisor_monitor_observes_panics_once() {
        use std::sync::atomic::AtomicUsize;

        let recoveries = Arc::new(AtomicUsize::new(0));
        let observed = Arc::clone(&recoveries);
        let supervisor = tokio::spawn(async {
            panic!("synthetic supervisor panic");
        });

        monitor_supervisor(supervisor, move |message| async move {
            assert!(message.contains("synthetic supervisor panic"));
            observed.fetch_add(1, Ordering::SeqCst);
        })
        .await;

        assert_eq!(recoveries.load(Ordering::SeqCst), 1);
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
        wait_for_started(
            &started,
            "blocking worker must publish its started handshake",
        )
        .await;

        cancel_token.cancel(CancelReason::User);
        let cancellation_won = tokio::time::timeout(Duration::from_millis(100), async {
            tokio::select! {
                _ = cancel_token.cancelled() => true,
                _ = &mut control => false,
            }
        })
        .await
        .expect("supervisor select must remain responsive");
        assert!(cancellation_won);
        let _ = control.await.expect("blocking control worker");
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn timed_out_pause_is_abandoned_and_owned_until_the_worker_finishes() {
        for _ in 0..100 {
            let GatedControlHarness {
                started,
                release,
                controller,
            } = gated_control_harness();
            let (response_tx, response_rx) = oneshot::channel();
            let mut pending_control = Some(PendingControl::new(
                controller,
                ProcessControlKind::Pause,
                false,
                response_tx,
                Duration::from_millis(1),
                PendingControlCleanup::default(),
            ));
            assert_eq!(
                pending_control.as_ref().expect("pending control").phase,
                ControlPhase::Requested
            );
            wait_for_started(&started, "control worker started handshake").await;

            assert!(matches!(
                wait_for_pending_control(&mut pending_control).await,
                PendingControlEvent::TimedOut
            ));
            let pending = pending_control.take().expect("pending control");
            let work = pending.into_timed_out_work();

            let response = response_rx.await.expect("timeout response");
            assert!(matches!(response, Err(ProcessControlError::Worker(_))));

            release.store(true, Ordering::Release);
            let joined = work
                .wait()
                .await
                .expect("owned blocking worker")
                .expect("blocking worker join");
            let (result, next_paused) = joined;
            result.expect("late control result");
            assert!(next_paused);
        }
    }

    struct FailingEventSink;

    impl TaskEventSink for FailingEventSink {
        fn emit(&self, _event: TaskDomainEvent) -> Result<(), String> {
            Err("synthetic event sink failure".to_string())
        }
    }

    struct GatedController {
        started: Arc<AtomicBool>,
        release: Arc<AtomicBool>,
    }

    struct GatedControlHarness {
        started: Arc<AtomicBool>,
        release: Arc<AtomicBool>,
        controller: Arc<dyn ProcessControl>,
    }

    fn gated_control_harness() -> GatedControlHarness {
        let started = Arc::new(AtomicBool::new(false));
        let release = Arc::new(AtomicBool::new(false));
        let controller = Arc::new(GatedController {
            started: Arc::clone(&started),
            release: Arc::clone(&release),
        });
        GatedControlHarness {
            started,
            release,
            controller,
        }
    }

    impl ProcessControl for GatedController {
        fn suspend(&self) -> Result<(), ProcessControlError> {
            self.started.store(true, Ordering::Release);
            while !self.release.load(Ordering::Acquire) {
                std::thread::yield_now();
            }
            Ok(())
        }

        fn resume(&self) -> Result<(), ProcessControlError> {
            Ok(())
        }
    }

    #[test]
    fn event_sink_failure_becomes_a_fatal_supervisor_error() {
        let mut terminal = TerminalState::default();
        let fatal = handle_reader_message(
            &FailingEventSink,
            ReaderMessage::Stderr("backend diagnostic".to_string()),
            &mut terminal,
        );

        assert!(fatal);
        match terminal.take() {
            Some(TerminalEvent::SupervisorError(payload)) => {
                assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
                assert!(payload.message.contains("synthetic event sink failure"));
            }
            _ => panic!("event sink failure must become the terminal supervisor error"),
        }
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
            PendingControlCleanup::default(),
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
    async fn compensation_uses_an_explicit_control_phase() {
        let mut pending = PendingControl::compensation(
            Arc::new(NoopController),
            true,
            false,
            PendingControlCleanup::default(),
        );

        assert_eq!(pending.phase, ControlPhase::Compensation);
        let PendingControlEvent::Finished(result) = pending.wait().await else {
            panic!("compensation must complete");
        };
        let (result, next_paused) = result.expect("compensation worker join");
        result.expect("compensation result");
        assert!(!next_paused);
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
    fn sleeping_process_group() -> ProcessGroupChild {
        let mut command = tokio::process::Command::new("cmd");
        command
            .args(["/C", "ping -n 30 127.0.0.1 >NUL"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        crate::tasks::builder::spawn_no_window_group(&mut command)
            .expect("spawn sleeping process group")
    }

    #[cfg(not(target_os = "windows"))]
    fn sleeping_process_group() -> ProcessGroupChild {
        let mut command = tokio::process::Command::new("sh");
        command
            .args(["-c", "sleep 30"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        crate::tasks::builder::spawn_no_window_group(&mut command)
            .expect("spawn sleeping process group")
    }

    struct StateLifecycle(Arc<TaskState>);

    impl TaskLifecyclePort for StateLifecycle {
        fn begin_reaping<'a>(
            &'a self,
            lease: &'a StartLease,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.begin_reaping(lease).await })
        }

        fn cancel_owned<'a>(
            &'a self,
            lease: &'a StartLease,
            reason: CancelReason,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.cancel_owned(lease, reason).await })
        }

        fn seal_owned<'a>(
            &'a self,
            lease: &'a StartLease,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.seal_owned(lease).await })
        }

        fn finish_once<'a>(
            &'a self,
            lease: &'a StartLease,
            before_release: Box<dyn FnOnce() + Send + 'static>,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.finish_once(lease, before_release).await })
        }

        fn fail_cleanup_once<'a>(
            &'a self,
            lease: &'a StartLease,
            terminal: Box<dyn FnOnce() + Send + 'static>,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.fail_cleanup_once(lease, terminal).await })
        }

        fn own_cleanup_observer<'a>(
            &'a self,
            lease: &'a StartLease,
            observer: JoinHandle<()>,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.own_cleanup_observer(lease, observer).await })
        }

        fn confirm_cleanup<'a>(
            &'a self,
            lease: &'a StartLease,
        ) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> {
            Box::pin(async move { self.0.confirm_cleanup(lease).await })
        }
    }

    #[derive(Default)]
    struct RecordingEventSink {
        events: Mutex<Vec<&'static str>>,
    }

    impl TaskEventSink for RecordingEventSink {
        fn emit(&self, event: TaskDomainEvent) -> Result<(), String> {
            let kind = match event {
                TaskDomainEvent::Progress(_) => "progress",
                TaskDomainEvent::ResumeStatus(_) => "resume-status",
                TaskDomainEvent::Log(_) => "log",
                TaskDomainEvent::Completed(_) => "completed",
                TaskDomainEvent::Error(_) => "error",
                TaskDomainEvent::Cancelled(_) => "cancelled",
            };
            self.events.lock().expect("event lock").push(kind);
            Ok(())
        }
    }

    struct UnknownStateController;

    impl ProcessControl for UnknownStateController {
        fn suspend(&self) -> Result<(), ProcessControlError> {
            Err(ProcessControlError::StateUnknown(
                "synthetic rollback failure".to_string(),
            ))
        }

        fn resume(&self) -> Result<(), ProcessControlError> {
            Ok(())
        }
    }

    #[tokio::test]
    async fn session_constructor_immediately_couples_process_owner_and_reap_ticket() {
        let state = Arc::new(TaskState::default());
        let lease = state.reserve_start().await.expect("reserve task slot");
        let (_control_tx, control_rx) = mpsc::channel(1);
        let (output_tx, output_rx) = mpsc::channel(1);
        drop(output_tx);
        let event_sink: Arc<dyn TaskEventSink> = Arc::new(RecordingEventSink::default());
        let lifecycle: Arc<dyn TaskLifecyclePort> = Arc::new(StateLifecycle(Arc::clone(&state)));
        let dependencies =
            SupervisorDependencies::new(event_sink, lifecycle, Arc::new(NoopController));
        let io = SupervisorIo::new(
            control_rx,
            output_rx,
            tokio::spawn(async {}),
            tokio::spawn(async {}),
            tokio::spawn(async {}),
            StderrCapture::new(),
        );

        let (session, mut recovery) = TaskSupervisorSession::new(
            sleeping_process_group(),
            lease.clone(),
            dependencies,
            io,
            Arc::new(Mutex::new(std::time::Instant::now())),
        );
        let pid = session.process.child.id().expect("owned process id");
        assert_eq!(session.process.reap_ticket.current(), None);
        assert_eq!(recovery.reap_ticket.current(), None);

        drop(session);

        assert_eq!(
            recovery
                .reap_ticket
                .wait_bounded(StartTaskSpec::TERMINATION_TIMEOUT)
                .await,
            Some(ReapOutcome::Reaped)
        );
        assert_process_exited(pid, StartTaskSpec::TERMINATION_TIMEOUT).await;
        state.rollback_start(&lease).await;
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn unknown_process_control_state_forces_kill_reap_and_one_terminal_event() {
        let state = Arc::new(TaskState::default());
        let lease = state.reserve_start().await.expect("reserve task slot");
        let (control_tx, control_rx) = mpsc::channel(2);
        state
            .activate(&lease, control_tx.clone())
            .await
            .expect("activate task");
        let (output_tx, output_rx) = mpsc::channel(1);
        drop(output_tx);
        let events = Arc::new(RecordingEventSink::default());
        let event_sink: Arc<dyn TaskEventSink> = events.clone();
        let lifecycle: Arc<dyn TaskLifecyclePort> = Arc::new(StateLifecycle(Arc::clone(&state)));
        let progress_beat = Arc::new(Mutex::new(std::time::Instant::now()));
        let dependencies =
            SupervisorDependencies::new(event_sink, lifecycle, Arc::new(UnknownStateController));
        let io = SupervisorIo::new(
            control_rx,
            output_rx,
            tokio::spawn(async {}),
            tokio::spawn(async {}),
            tokio::spawn(async {}),
            StderrCapture::new(),
        );
        let (session, _recovery) = TaskSupervisorSession::new(
            sleeping_process_group(),
            lease.clone(),
            dependencies,
            io,
            progress_beat,
        );
        let pid = session.process.child.id().expect("live test process");
        let supervisor = tokio::spawn(run_task_supervisor(session));
        let (response_tx, response_rx) = oneshot::channel();
        control_tx
            .send(TaskControlMessage {
                kind: ProcessControlKind::Pause,
                response: response_tx,
            })
            .await
            .expect("send pause");

        assert!(matches!(
            response_rx.await.expect("control response"),
            Err(ProcessControlError::StateUnknown(_))
        ));
        tokio::time::timeout(StartTaskSpec::TERMINATION_TIMEOUT, supervisor)
            .await
            .expect("supervisor cleanup deadline")
            .expect("supervisor join");
        assert_process_exited(pid, StartTaskSpec::TERMINATION_TIMEOUT).await;
        assert_eq!(
            events.events.lock().expect("event lock").as_slice(),
            ["error"]
        );
        let next = state
            .reserve_start()
            .await
            .expect("cleanup releases task slot");
        state.rollback_start(&next).await;
    }

    #[tokio::test]
    async fn dropping_a_live_supervised_child_kills_and_reaps_it() {
        let (child, mut ticket) =
            ProcessGroupOwner::new(sleeping_process_group(), "test process group");
        let pid = child.id().expect("live supervised pid");

        drop(child);

        assert_eq!(
            ticket
                .wait_bounded(StartTaskSpec::TERMINATION_TIMEOUT)
                .await,
            Some(ReapOutcome::Reaped)
        );
        assert_process_exited(pid, StartTaskSpec::TERMINATION_TIMEOUT).await;
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn panicking_supervisor_reaps_child_releases_slot_and_finishes_once() {
        let (state, lease, _control_rx) = active_task_fixture().await;

        let (child, mut reap_ticket) =
            ProcessGroupOwner::new(sleeping_process_group(), "panic test process group");
        let pid = child.id().expect("live supervised pid");
        let supervisor = tokio::spawn(async move {
            assert_eq!(child.id(), Some(pid));
            panic!("synthetic live-child supervisor panic");
        });

        let terminal_count = Arc::new(AtomicUsize::new(0));
        let recovery_count = Arc::clone(&terminal_count);
        let recovery_state = Arc::clone(&state);
        let recovery_lease = lease.clone();
        monitor_supervisor(supervisor, move |message| async move {
            assert!(message.contains("synthetic live-child supervisor panic"));
            assert!(recovery_state.begin_reaping(&recovery_lease).await);
            assert_eq!(reap_ticket.wait().await, ReapOutcome::Reaped);
            assert!(
                recovery_state
                    .finish_once(&recovery_lease, move || {
                        recovery_count.fetch_add(1, Ordering::SeqCst);
                    })
                    .await
            );
            assert!(
                !recovery_state.finish_once(&recovery_lease, || {}).await,
                "duplicate recovery must not emit a second terminal event"
            );
        })
        .await;

        assert_eq!(terminal_count.load(Ordering::SeqCst), 1);
        let next_lease = state
            .reserve_start()
            .await
            .expect("panic recovery must release the task slot");
        state.rollback_start(&next_lease).await;
        assert_process_exited(pid, StartTaskSpec::TERMINATION_TIMEOUT).await;
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn panic_recovery_keeps_slot_closed_until_active_control_work_finishes() {
        let (state, lease, _control_rx) = active_task_fixture().await;

        let (child, reap_ticket) =
            ProcessGroupOwner::new(sleeping_process_group(), "panic control test process group");
        let pid = child.id().expect("live supervised pid");
        drop(child);

        let GatedControlHarness {
            started,
            release,
            controller,
        } = gated_control_harness();
        let control_cleanup = PendingControlCleanup::default();
        control_cleanup
            .start(|| spawn_process_control_work(controller, ProcessControlKind::Pause, false));
        wait_for_started(&started, "control worker started handshake").await;

        let events = Arc::new(RecordingEventSink::default());
        let event_sink: Arc<dyn TaskEventSink> = events.clone();
        let lifecycle: Arc<dyn TaskLifecyclePort> = Arc::new(StateLifecycle(Arc::clone(&state)));
        let recovery = tokio::spawn(recover_supervisor_join_failure(
            SupervisorRecoveryContext {
                event_sink,
                lifecycle,
                lease: lease.clone(),
                stderr_capture: StderrCapture::new(),
                reap_ticket,
                control_cleanup,
            },
            "synthetic panic with active control".to_string(),
        ));

        tokio::task::yield_now().await;
        assert!(matches!(
            state.reserve_start().await,
            Err(crate::tasks::state::TaskStateError::AlreadyRunning)
        ));

        release.store(true, Ordering::Release);
        tokio::time::timeout(StartTaskSpec::TERMINATION_TIMEOUT, recovery)
            .await
            .expect("panic recovery deadline")
            .expect("panic recovery join");
        assert_process_exited(pid, StartTaskSpec::TERMINATION_TIMEOUT).await;
        assert_eq!(
            events.events.lock().expect("event lock").as_slice(),
            ["error"]
        );

        let next = state
            .reserve_start()
            .await
            .expect("completed control and reap release the task slot");
        state.rollback_start(&next).await;
    }

    #[tokio::test]
    async fn requested_process_group_kill_is_observed_and_reaped() {
        let (mut child, _ticket) =
            ProcessGroupOwner::new(sleeping_process_group(), "kill test process group");
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
