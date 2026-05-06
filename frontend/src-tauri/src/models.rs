use crate::protocol::TaskErrorCode;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use tokio::sync::{mpsc, oneshot, Mutex};
use ts_rs::TS;

pub type JsonMap = BTreeMap<String, serde_json::Value>;

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct DecodeConfig {
    pub mode: String,
    #[ts(optional)]
    pub hwaccel: Option<String>,
    #[ts(optional)]
    pub hwaccel_device: Option<String>,
    #[ts(optional)]
    pub decoder: Option<String>,
    #[serde(default)]
    #[ts(type = "Record<string, string | number | boolean>")]
    pub options: JsonMap,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct InterpolationConfig {
    pub enabled: bool,
    pub target_fps: f64,
    pub multi: u32,
    pub model: String,
    #[serde(default)]
    #[ts(optional)]
    pub onnx_model: Option<String>,
    pub scale: f64,
    pub fp16: bool,
    pub tensor_backend: String,
    #[serde(default = "default_engine")]
    pub engine: String,
}

fn default_engine() -> String {
    "cuda".to_string()
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct SuperResolutionConfig {
    pub enabled: bool,
    pub scale_factor: f64,
    pub algorithm: String,
    #[serde(default)]
    #[ts(optional)]
    pub onnx_model: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct AnimeConfig {
    pub enabled: bool,
    pub profile: String,
    pub denoise: u32,
    pub edge_boost: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct FilterStep {
    pub kind: String,
    pub enabled: bool,
    #[serde(default)]
    #[ts(type = "Record<string, string | number | boolean>")]
    pub params: serde_json::Map<String, serde_json::Value>,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct PreprocessConfig {
    pub enabled: bool,
    #[serde(default)]
    pub filters: Vec<FilterStep>,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct PostprocessConfig {
    pub enabled: bool,
    #[serde(default)]
    pub filters: Vec<FilterStep>,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct WorkflowConfig {
    pub fps_mode: String,
    pub process_order: String,
    pub interpolation: InterpolationConfig,
    pub super_resolution: SuperResolutionConfig,
    pub anime: AnimeConfig,
    #[serde(default = "default_preprocess")]
    pub preprocess: PreprocessConfig,
    #[serde(default = "default_postprocess")]
    pub postprocess: PostprocessConfig,
}

fn default_preprocess() -> PreprocessConfig {
    PreprocessConfig {
        enabled: false,
        filters: Vec::new(),
    }
}

fn default_postprocess() -> PostprocessConfig {
    PostprocessConfig {
        enabled: false,
        filters: Vec::new(),
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct RateControlConfig {
    pub mode: String,
    #[ts(type = "number | string")]
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EncodeConfig {
    pub codec: String,
    pub family: String,
    pub container: String,
    pub keep_audio: bool,
    pub rate_control: RateControlConfig,
    #[serde(default)]
    #[ts(type = "Record<string, string | number | boolean>")]
    pub options: JsonMap,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct OutputConfig {
    pub output_dir: String,
    pub open_on_complete: bool,
    #[ts(type = "number")]
    pub segment_frames: u64,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct WorkbenchPreset {
    pub decode_config: DecodeConfig,
    pub workflow_config: WorkflowConfig,
    pub encode_config: EncodeConfig,
    pub output_config: OutputConfig,
}

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

#[derive(Debug, Clone, Copy)]
pub enum TaskControlKind {
    Cancel,
    Pause,
    Resume,
}

pub struct TaskControlMessage {
    pub kind: TaskControlKind,
    pub response: oneshot::Sender<Result<(), String>>,
}

#[derive(Clone)]
pub struct RunningTask {
    pub control_tx: mpsc::Sender<TaskControlMessage>,
}

#[derive(Default)]
pub struct TaskState {
    pub current: Mutex<Option<RunningTask>>,
}

#[cfg(test)]
mod tests {
    use super::*;
}
