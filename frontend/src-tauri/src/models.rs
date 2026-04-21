use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use command_group::AsyncGroupChild;
use tokio::sync::Mutex;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskRequest {
    pub input_path: String,
    pub algorithm: String,
    pub output_path: Option<String>,
    pub output_dir: Option<String>,
    pub temp_dir: Option<String>,
    pub fps: f64,
    pub fps_mode: String,
    pub target_fps: Option<f64>,
    pub codec: String,
    pub crf: u32,
    pub preset: String,
    pub backend: String,
    pub multi: u32,
    pub model: String,
    pub scale: f64,
    pub fp16: bool,
    pub enable_interpolation: bool,
    pub enable_super_resolution: bool,
    pub process_order: String,
    pub sr_scale_factor: f64,
    pub sr_algorithm: String,
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
