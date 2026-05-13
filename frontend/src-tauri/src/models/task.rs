use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

use crate::models::config::{DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig};

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskRequest {
    pub input_path: String,
    pub decode_config: DecodeConfig,
    pub workflow_config: WorkflowConfig,
    pub encode_config: EncodeConfig,
    pub output_config: OutputConfig,
    #[serde(default)]
    #[ts(optional)]
    pub resume_mode: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskProgressPayload {
    #[ts(type = "number")]
    pub current: u64,
    #[ts(type = "number")]
    pub total: u64,
    pub percent: f64,
    pub stage: String,
    #[ts(type = "number")]
    pub stage_index: u64,
    #[ts(type = "number")]
    pub stage_total: u64,
    /// Phase D.2.3 — optional pipeline observability bag. Carries the
    /// snapshot from ``backend/app/processing/streaming/metrics.py``:
    /// queue depths, processed-frame counter, measured fps, elapsed
    /// seconds, per-stage durations. Free-form so the schema can evolve
    /// without forcing a Rust + ts-rs roundtrip every iteration; UI
    /// consumers should treat unknown sub-keys as best-effort.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    #[ts(type = "Record<string, unknown> | null")]
    pub metrics: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskCompletedPayload {
    pub output_path: String,
    #[ts(type = "number")]
    pub processed_frames: u64,
    pub time_seconds: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TaskErrorCode {
    MissingFfmpeg,
    MissingModel,
    MissingTensorBackend,
    MissingPythonDependency,
    Cancelled,
    ProcessFailed,
    SpawnFailed,
    RuntimePanic,
    InvalidInput,
    InvalidConfig,
    ResumeConflict,
    IoError,
    SchemaMismatch,
    PersistenceFailed,
}

impl TaskErrorCode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::MissingFfmpeg => "missing_ffmpeg",
            Self::MissingModel => "missing_model",
            Self::MissingTensorBackend => "missing_tensor_backend",
            Self::MissingPythonDependency => "missing_python_dependency",
            Self::Cancelled => "cancelled",
            Self::ProcessFailed => "process_failed",
            Self::SpawnFailed => "spawn_failed",
            Self::RuntimePanic => "runtime_panic",
            Self::InvalidInput => "invalid_input",
            Self::InvalidConfig => "invalid_config",
            Self::ResumeConflict => "resume_conflict",
            Self::IoError => "io_error",
            Self::SchemaMismatch => "schema_mismatch",
            Self::PersistenceFailed => "persistence_failed",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskLogPayload {
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct ResumeStatusPayload {
    pub resumed: bool,
    #[ts(type = "number")]
    pub completed_chunks: u64,
    #[ts(type = "number")]
    pub completed_output_frames: u64,
    #[ts(type = "number")]
    pub start_source_frame: u64,
    #[ts(type = "number")]
    pub total_output_frames: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskErrorPayload {
    pub code: TaskErrorCode,
    pub message: String,
    #[ts(type = "Record<string, unknown> | null")]
    pub details: Option<serde_json::Value>,
}

/// Why a task entered the cancelled terminal state.
///
/// Phase D.1.2 — promoted from a `details.stalled` boolean in
/// ``TaskErrorPayload`` to a first-class enum on
/// ``TaskCancelledPayload``. Lets the frontend route the two cases
/// (user-initiated cancel vs. watchdog-triggered stall) by enum value
/// instead of digging into a free-form details bag.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TaskCancelledReason {
    /// The user pressed Cancel / Interrupt in the UI.
    User,
    /// The stall watchdog killed the backend after a long stdout silence.
    Stalled,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskCancelledPayload {
    pub reason: TaskCancelledReason,
    #[ts(type = "Record<string, unknown> | null")]
    pub details: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct VideoInfo {
    #[serde(rename = "type")]
    pub kind: String,
    pub fps: f64,
    #[ts(type = "number")]
    pub frames: u64,
    pub duration: f64,
    pub width: u32,
    pub height: u32,
    pub has_audio: bool,
    pub video_codec: String,
}
