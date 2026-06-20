use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

pub type JsonMap = serde_json::Map<String, serde_json::Value>;

// Phase D.3.4a — string fields with a small, stable value set are
// promoted to Rust enums. The serde wire format stays identical
// (``rename_all = "snake_case"``), but ts-rs now emits union literal
// types for the frontend, giving switch-case exhaustiveness checks. The
// Python Pydantic models still see them as plain ``str`` so backward
// compatibility with persisted preset JSON is preserved.

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum DecodeMode {
    Software,
    Hardware,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum FpsMode {
    Multi,
    Target,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum ProcessOrder {
    SuperResolutionThenInterpolation,
    FrameInterpolationThenSuperResolution,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TensorBackend {
    Pytorch,
    Paddle,
    Onnx,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum RateControlMode {
    Crf,
    Cq,
    Qp,
    Bitrate,
}

#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct DecodeConfig {
    pub mode: DecodeMode,
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
    #[serde(default = "default_interpolation_algorithm")]
    pub algorithm: String,
    pub model: String,
    #[serde(default)]
    #[ts(optional)]
    pub onnx_model: Option<String>,
    pub scale: f64,
    pub fp16: bool,
    pub tensor_backend: TensorBackend,
    #[serde(default = "default_engine")]
    pub engine: String,
}

fn default_engine() -> String {
    "cuda".to_string()
}

fn default_super_resolution_backend() -> TensorBackend {
    TensorBackend::Onnx
}

fn default_num_frames() -> u32 {
    10
}

fn default_auto_download_weights() -> bool {
    true
}

fn default_interpolation_algorithm() -> String {
    "rife".to_string()
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
    #[serde(default = "default_super_resolution_backend")]
    pub tensor_backend: TensorBackend,
    #[serde(default = "default_engine")]
    pub engine: String,
    #[serde(default = "default_num_frames")]
    pub num_frames: u32,
    #[serde(default = "default_auto_download_weights")]
    pub auto_download_weights: bool,
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
    pub params: JsonMap,
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
    pub fps_mode: FpsMode,
    pub process_order: ProcessOrder,
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
    pub mode: RateControlMode,
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
    // Phase 18 — ``output_dir`` 改为 ``Option<String>``。用户要求"强制选择
    // 输出目录,不使用默认目录",Option 把"空 / 未选"提升到 type level,
    // wire 上的 ``null`` 与 ``""`` 都表示"未填",由 Pydantic
    // ``OutputConfig.output_dir`` validator(``min_length=1`` + 非空白)在
    // backend 入口拒掉。Rust 端不再有兜底逻辑,序列化为 ``null`` 时 Python
    // 收到 ``None`` → Pydantic alias resolution 失败 / ValidationError →
    // INVALID_CONFIG。
    pub output_dir: Option<String>,
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
