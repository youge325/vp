use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use command_group::AsyncGroupChild;
use tokio::sync::Mutex;

pub type JsonMap = BTreeMap<String, serde_json::Value>;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DecodeConfig {
    pub mode: String,
    pub hwaccel: Option<String>,
    pub hwaccel_device: Option<String>,
    pub decoder: Option<String>,
    #[serde(default)]
    pub options: JsonMap,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InterpolationConfig {
    pub enabled: bool,
    pub target_fps: f64,
    pub multi: u32,
    pub model: String,
    pub scale: f64,
    pub fp16: bool,
    pub tensor_backend: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SuperResolutionConfig {
    pub enabled: bool,
    pub scale_factor: f64,
    pub algorithm: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AnimeConfig {
    pub enabled: bool,
    pub profile: String,
    pub denoise: u32,
    pub edge_boost: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowConfig {
    pub fps_mode: String,
    pub process_order: String,
    pub interpolation: InterpolationConfig,
    pub super_resolution: SuperResolutionConfig,
    pub anime: AnimeConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RateControlConfig {
    pub mode: String,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EncodeConfig {
    pub codec: String,
    pub family: String,
    pub container: String,
    pub keep_audio: bool,
    pub rate_control: RateControlConfig,
    #[serde(default)]
    pub options: JsonMap,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OutputConfig {
    pub output_dir: String,
    pub open_on_complete: bool,
    pub segment_frames: u64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskRequest {
    pub input_path: String,
    pub decode_config: DecodeConfig,
    pub workflow_config: WorkflowConfig,
    pub encode_config: EncodeConfig,
    pub output_config: OutputConfig,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskProgressPayload {
    pub current: u64,
    pub total: u64,
    pub percent: f64,
    pub stage: String,
    pub stage_index: u64,
    pub stage_total: u64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskCompletedPayload {
    pub output_path: String,
    pub processed_frames: u64,
    pub time_seconds: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct TaskLogPayload {
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct TaskErrorPayload {
    pub code: String,
    pub message: String,
    pub details: Option<serde_json::Value>,
}

#[derive(Clone)]
pub struct RunningTask {
    pub child: Arc<Mutex<AsyncGroupChild>>,
    pub cancelled: Arc<AtomicBool>,
    pub terminal_sent: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct TaskState {
    pub current: Mutex<Option<RunningTask>>,
}
