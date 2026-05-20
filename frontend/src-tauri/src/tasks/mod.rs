pub mod builder;
pub mod cancellation;
pub mod commands;
pub mod control;
pub mod controller;
pub mod envelope;
pub mod handle;
pub mod oneshot;
pub mod readers;
pub mod spawn;
pub mod state;
pub mod stderr;

use tokio::sync::oneshot as TokioOneshot;

use crate::process_control::ProcessControlError;

pub use builder::build_inspect_output_args;
pub use control::{cancel_running_task, pause_running_task, resume_running_task};
pub use oneshot::run_single_cli_command;
pub use spawn::spawn_task;
pub use state::TaskState;

// Phase 3.1 — TaskControlKind / TaskControlMessage 从 state.rs 上提到 mod.rs,
// 打破 handle.rs <-> state.rs 的隐式循环依赖。

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskControlKind {
    Pause,
    Resume,
}

pub struct TaskControlMessage {
    pub kind: TaskControlKind,
    /// Phase 5a — typed reply channel. Previously this was
    /// ``Result<(), String>``, which forced every layer between the
    /// process controller and the IPC boundary to round-trip through
    /// a stringly-typed error and lose the original ``io::Error``
    /// source. Carrying the structured error all the way out keeps
    /// the [`ShellError`] conversion (and the eventual frontend
    /// [`TaskErrorCode`]) honest.
    ///
    /// [`ShellError`]: crate::error::ShellError
    /// [`TaskErrorCode`]: crate::protocol::TaskErrorCode
    pub response: TokioOneshot::Sender<Result<(), ProcessControlError>>,
}
