use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

pub type JsonMap = serde_json::Map<String, serde_json::Value>;

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
    #[serde(default = "default_interpolation_algorithm")]
    pub algorithm: String,
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
