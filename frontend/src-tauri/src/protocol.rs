use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "kebab-case")]
#[ts(export, export_to = "../../src/types/generated/")]
// Variants intentionally mirror the full Tauri event names exported to TypeScript.
#[allow(clippy::enum_variant_names)]
pub(crate) enum TaskEventName {
    TaskProgress,
    TaskCompleted,
    TaskError,
    TaskCancelled,
    TaskLog,
    TaskResumeStatus,
}

impl TaskEventName {
    pub(crate) fn as_str(&self) -> &'static str {
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

// Phase D.3.5 — ``TERMINAL_PROGRESS_PREFIX`` was a leftover constant
// from before the NDJSON envelope took over progress reporting. The
// Rust side never reads it (the prefix only matters inside Python's
// reporter and inside frontend TaskConsole log-folding logic), so
// keeping it here just invited bit-rot. The frontend has its own copy
// at ``frontend/src/types/protocol/events.ts``.
