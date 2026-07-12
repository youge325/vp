pub(crate) mod builder;
pub(crate) mod cancellation;
pub(crate) mod commands;
pub(crate) mod control;
pub(crate) mod controller;
pub(crate) mod envelope;
pub(crate) mod handle;
pub(crate) mod oneshot;
pub(crate) mod readers;
pub(crate) mod spawn;
pub(crate) mod state;
pub(crate) mod stderr;

use serde::Deserialize;
use tokio::sync::oneshot as TokioOneshot;

use crate::process_control::ProcessControlError;

pub(crate) use builder::build_inspect_output_args;
pub(crate) use control::{cancel_running_task, send_task_control};
pub(crate) use oneshot::run_single_cli_command;
pub(crate) use spawn::spawn_task;
pub(crate) use state::TaskState;

// Phase 3.1 — TaskControlKind / TaskControlMessage 从 state.rs 上提到 mod.rs,
// 打破 handle.rs <-> state.rs 的隐式循环依赖。
// Phase A — 加 ``Deserialize`` + ``serde(rename_all = "lowercase")``,
// 让前端可以通过 ``control_task({ kind: "pause" | "resume" })`` 直接传枚举,
// 不需要 Rust 端再做一层手工 dispatch。

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub(crate) enum TaskControlKind {
    Pause,
    Resume,
}

pub(crate) struct TaskControlMessage {
    pub(crate) kind: TaskControlKind,
    /// Phase 5a — typed reply channel. Previously this was
    /// ``Result<(), String>``, which forced every layer between the
    /// process controller and the IPC boundary to round-trip through
    /// a stringly-typed error and lose the original ``io::Error``
    /// source. Carrying the structured error all the way out keeps
    /// the [`ShellError`] conversion (and the eventual frontend
    /// [`TaskErrorCode`]) honest.
    ///
    /// [`ShellError`]: crate::error::ShellError
    /// [`TaskErrorCode`]: crate::models::TaskErrorCode
    pub(crate) response: TokioOneshot::Sender<Result<(), ProcessControlError>>,
}
