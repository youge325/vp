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
    // Phase 2.1 — 拆分 BackendExit 为语义明确的变体。
    BackendNoJson,
    BackendEnvelope,
    ControllerUnavailable,
    BackendProbeFailed,
}

// Phase D.3.5 — ``TaskErrorCode::as_str`` was a hand-maintained string
// table that mirrored ``#[serde(rename_all = "snake_case")]``. It had
// zero call sites in the crate (every emit uses serde via
// ``TaskErrorPayload``) and was a known drift hazard. Removed; if a
// future caller needs the string, use ``serde_json::to_value`` or
// ``serde_plain::to_string`` instead.

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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum ResumeInspectionEventType {
    ResumeInspection,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum ResumePipelineKind {
    Streaming,
    FormatConversion,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct ResumeInspectionResult {
    #[serde(rename = "type")]
    #[ts(rename = "type")]
    pub event_type: ResumeInspectionEventType,
    #[serde(rename = "pipeline_kind")]
    #[ts(rename = "pipeline_kind")]
    pub pipeline_kind: ResumePipelineKind,
    pub output_path: String,
    #[serde(rename = "input_path")]
    #[ts(rename = "input_path")]
    pub input_path: String,
    pub final_exists: bool,
    pub sidecar_exists: bool,
    pub signature_match: bool,
    #[ts(type = "number")]
    pub completed_chunks: u64,
    #[ts(type = "number")]
    pub completed_output_frames: u64,
    #[ts(type = "number")]
    pub next_source_frame: u64,
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
    pub fps: f64,
    pub width: u32,
    pub height: u32,
    pub video_codec: String,
}

#[cfg(test)]
mod video_info_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn video_info_ignores_backend_envelope_and_removed_diagnostics() {
        let raw = json!({
            "type": "info",
            "fps": 24.0,
            "frames": 240,
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "hasAudio": true,
            "videoCodec": "h264"
        });

        let info: VideoInfo = serde_json::from_value(raw).expect("video info");
        assert_eq!(
            serde_json::to_value(info).expect("serialize video info"),
            json!({ "fps": 24.0, "width": 1920, "height": 1080, "videoCodec": "h264" })
        );
    }

    #[test]
    fn resume_inspection_validates_the_mixed_case_backend_contract() {
        let raw = json!({
            "type": "resume_inspection",
            "pipeline_kind": "streaming",
            "outputPath": "D:/out.mp4",
            "input_path": "D:/in.mp4",
            "finalExists": true,
            "sidecarExists": true,
            "signatureMatch": true,
            "completedChunks": 2,
            "completedOutputFrames": 120,
            "nextSourceFrame": 60,
            "totalOutputFrames": 240
        });

        let inspection: ResumeInspectionResult =
            serde_json::from_value(raw.clone()).expect("resume inspection");
        assert_eq!(
            inspection.event_type,
            ResumeInspectionEventType::ResumeInspection
        );
        assert_eq!(inspection.pipeline_kind, ResumePipelineKind::Streaming);
        assert_eq!(
            serde_json::to_value(inspection).expect("serialize resume inspection"),
            raw
        );
    }
}
