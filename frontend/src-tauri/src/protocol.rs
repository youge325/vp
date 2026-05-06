use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

// Re-export so existing callers do not break.
pub use crate::models::TaskErrorCode;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "kebab-case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TaskEventName {
    TaskProgress,
    TaskCompleted,
    TaskError,
    TaskCancelled,
    TaskLog,
    TaskResumeStatus,
}

impl TaskEventName {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TaskProgress => "task-progress",
            Self::TaskCompleted => "task-completed",
            Self::TaskError => "task-error",
            Self::TaskCancelled => "task-cancelled",
            Self::TaskLog => "task-log",
            Self::TaskResumeStatus => "task-resume-status",
        }
    }
}

pub const TERMINAL_PROGRESS_PREFIX: &str = "[VP_PROGRESS]";
