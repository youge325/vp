// Generated from contracts/ipc-manifest.json. Do not edit.

use serde::Deserialize;

use crate::models::{
    BackendTaskErrorPayload, ResumeStatusPayload, TaskCompletedPayload, TaskProgressPayload,
};

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
pub(crate) enum BackendTaskEnvelope {
    #[serde(rename = "progress")]
    Progress(TaskProgressPayload),
    #[serde(rename = "completed")]
    Completed(TaskCompletedPayload),
    #[serde(rename = "error")]
    Error(BackendTaskErrorPayload),
    #[serde(rename = "resume_status")]
    ResumeStatus(ResumeStatusPayload),
}
