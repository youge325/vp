//! Bounded pause/resume coordination for the supervisor event loop.

use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::oneshot;
use tokio::task::JoinHandle;

use crate::process_control::{ProcessControl, ProcessControlError};
use crate::tasks::cleanup::PendingControlCleanup;
use crate::tasks::ProcessControlKind;

pub(super) const PROCESS_CONTROL_TIMEOUT: Duration = Duration::from_secs(4);

pub(super) struct PendingControl {
    work: PendingControlCleanup,
    deadline: Pin<Box<tokio::time::Sleep>>,
    timeout: Duration,
    pub(super) response: Option<oneshot::Sender<Result<(), ProcessControlError>>>,
    initial_paused: bool,
    shutdown: ShutdownDirective,
    pub(super) phase: ControlPhase,
}

#[derive(Clone, Copy)]
pub(super) enum ControlRestoration {
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
pub(super) enum ControlPhase {
    Requested,
    Compensation,
}

pub(super) enum PendingControlEvent {
    Finished(Result<(Result<(), ProcessControlError>, bool), tokio::task::JoinError>),
    TimedOut,
}

impl PendingControl {
    pub(super) fn new(
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

    pub(super) fn reject_response(&mut self, message: &str) {
        if let Some(response) = self.response.take() {
            let _ = response.send(Err(ProcessControlError::Worker(message.to_string())));
        }
    }

    pub(super) fn compensation(
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

    pub(super) fn apply_restoration(&mut self, restoration: ControlRestoration) {
        if self.shutdown == ShutdownDirective::Abandon {
            return;
        }
        self.shutdown = match restoration {
            ControlRestoration::Target(target) => ShutdownDirective::RestoreTo(target),
            ControlRestoration::Abandon => ShutdownDirective::Abandon,
        };
    }

    pub(super) fn compensation_target(&self, next_paused: bool) -> Option<bool> {
        match self.shutdown {
            ShutdownDirective::RestoreTo(target) if next_paused != target => Some(target),
            _ => None,
        }
    }

    pub(super) fn into_abandoned_work(mut self, message: &str) -> PendingControlCleanup {
        self.apply_restoration(ControlRestoration::Abandon);
        self.reject_response(message);
        self.work
    }

    pub(super) fn into_timed_out_work(mut self) -> PendingControlCleanup {
        self.apply_restoration(ControlRestoration::Abandon);
        self.reject_response(&format!(
            "operation timed out after {} seconds",
            self.timeout.as_secs_f64()
        ));
        self.work
    }

    pub(super) async fn wait(&mut self) -> PendingControlEvent {
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

#[cfg(test)]
mod tests {
    use super::*;

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
    fn pause_and_resume_are_idempotent() {
        let mut paused = false;
        handle_pause_resume(&NoopController, ProcessControlKind::Pause, &mut paused).unwrap();
        handle_pause_resume(&NoopController, ProcessControlKind::Pause, &mut paused).unwrap();
        assert!(paused);
        handle_pause_resume(&NoopController, ProcessControlKind::Resume, &mut paused).unwrap();
        assert!(!paused);
    }

    #[test]
    fn failed_control_does_not_change_pause_state() {
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
}
