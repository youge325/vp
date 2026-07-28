// Generated from contracts/ipc-manifest.json. Do not edit.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
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
    pub(crate) const fn as_str(self) -> &'static str {
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
