mod builder;
mod cancellation;
pub(crate) mod commands;
mod control;
mod controller;
mod envelope;
mod handle;
mod oneshot;
mod readers;
mod spawn;
mod state;
mod stderr;
mod subprocess;
#[cfg(test)]
mod test_support;

use tokio::sync::oneshot as TokioOneshot;

use crate::error::ShellError;
use crate::generated::TaskControlKind;
use crate::process_control::ProcessControlError;

pub(crate) use builder::build_resume_inspection_input;
pub(crate) use control::send_task_control;
pub(crate) use oneshot::run_single_cli_command;
pub(crate) use spawn::spawn_task;
pub(crate) use state::{TaskState, TaskStateError};

#[derive(Debug)]
pub(crate) enum TaskApplicationError {
    State(TaskStateError),
    Shell(ShellError),
}

impl From<TaskStateError> for TaskApplicationError {
    fn from(error: TaskStateError) -> Self {
        Self::State(error)
    }
}

impl From<ShellError> for TaskApplicationError {
    fn from(error: ShellError) -> Self {
        Self::Shell(error)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ProcessControlKind {
    Pause,
    Resume,
}

pub(crate) struct TaskControlMessage {
    pub(crate) kind: ProcessControlKind,
    /// Typed reply preserves process-control error context to the IPC boundary.
    pub(crate) response: TokioOneshot::Sender<Result<(), ProcessControlError>>,
}
