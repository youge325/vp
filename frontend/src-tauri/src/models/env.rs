use std::collections::HashMap;

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use ts_rs::TS;

use crate::models::config::{RateControlMode, TensorBackend};

macro_rules! string_enum {
    ($name:ident { $($variant:ident),+ $(,)? }) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
        #[serde(rename_all = "snake_case")]
        #[ts(export, export_to = "../../src/types/generated/")]
        pub enum $name {
            $($variant),+
        }
    };
}

string_enum!(AlgorithmFamily {
    Rife,
    OnnxSuperResolution,
    PaddleganVsr,
});
string_enum!(CapabilityOptionKind {
    Boolean,
    Number,
    String,
    Choice,
});
string_enum!(CodecProfileFamily {
    Cpu,
    Nvidia,
    Intel,
    Software,
});
string_enum!(EnvironmentCheckSource { Cache, Probe });
string_enum!(GpuVendor {
    Nvidia,
    Intel,
    Amd,
    Hygon,
    Other,
});
string_enum!(InferenceEngine {
    Cuda,
    Tensorrt,
    Dcu,
});
string_enum!(InputFrameMode {
    None,
    EditableChunk,
    FixedWindow,
});

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "kebab-case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum RuntimeMode {
    External,
    Bundled,
    ExpectedBundled,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct CapabilityChoice {
    pub label: String,
    #[ts(type = "string | number | boolean")]
    pub value: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct CapabilityOptionSpec {
    pub name: String,
    pub label: String,
    pub r#type: CapabilityOptionKind,
    #[ts(type = "string | number | boolean | null")]
    pub default_value: Value,
    #[serde(default)]
    pub choices: Vec<CapabilityChoice>,
    #[serde(default)]
    pub min: Option<f64>,
    #[serde(default)]
    pub max: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct RateControlModeSpec {
    pub mode: RateControlMode,
    pub label: String,
    #[ts(type = "string | number")]
    pub default_value: Value,
    pub unit: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct HardwareDeviceOptionSpec {
    pub value: String,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct CodecProfileSpec {
    pub name: String,
    pub label: String,
    pub family: CodecProfileFamily,
    pub codec: String,
    pub available: bool,
    #[serde(default)]
    pub hardware_devices: Vec<String>,
    #[serde(default)]
    pub options: Vec<CapabilityOptionSpec>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    pub rate_control_modes: Option<Vec<RateControlModeSpec>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    pub hardware_device_options: Option<HashMap<String, Vec<HardwareDeviceOptionSpec>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct GpuAdapter {
    pub name: String,
    pub vendor: GpuVendor,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct FfmpegInfo {
    pub available: bool,
    #[serde(default)]
    pub hwaccels: Vec<String>,
    #[serde(default)]
    pub encoder_profiles: Vec<CodecProfileSpec>,
    #[serde(default)]
    pub decoder_profiles: Vec<CodecProfileSpec>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct GpuInfo {
    #[serde(default)]
    pub adapters: Vec<GpuAdapter>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TensorEngines {
    #[serde(default)]
    pub pytorch: Vec<InferenceEngine>,
    #[serde(default)]
    pub paddle: Vec<InferenceEngine>,
    #[serde(default)]
    pub onnx: Vec<InferenceEngine>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct ModelEngineMetricInfo {
    #[serde(default)]
    pub gflops_per_megapixel: Option<f64>,
    #[serde(default)]
    pub activation_bytes_per_megapixel: Option<f64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub runtime_overhead_bytes: Option<u64>,
    #[serde(default)]
    pub runtime_frame_count: Option<u32>,
    #[serde(default)]
    pub input_modulo: Option<u32>,
    #[serde(default)]
    pub analysis_status: String,
    #[serde(default)]
    pub analysis_notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct ModelMetricInfo {
    #[serde(default)]
    #[ts(type = "number | null")]
    pub parameter_count: Option<u64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub parameter_bytes: Option<u64>,
    #[serde(default)]
    pub gflops_per_megapixel: Option<f64>,
    #[serde(default)]
    pub activation_bytes_per_megapixel: Option<f64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub runtime_overhead_bytes: Option<u64>,
    #[serde(default)]
    pub runtime_frame_count: Option<u32>,
    #[serde(default)]
    pub input_modulo: Option<u32>,
    #[serde(default)]
    pub analysis_status: String,
    #[serde(default)]
    pub analysis_notes: Vec<String>,
    #[serde(default)]
    pub engine_metrics: HashMap<String, ModelEngineMetricInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct ModelVariantInfo {
    pub name: String,
    pub label: String,
    pub metrics: ModelMetricInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct AlgorithmInfo {
    pub name: String,
    pub family: AlgorithmFamily,
    #[serde(default)]
    pub tensor_backends: Vec<TensorBackend>,
    pub models: Vec<String>,
    #[serde(default)]
    pub onnx_models: Vec<String>,
    #[serde(default)]
    pub model_details: Vec<ModelVariantInfo>,
    #[serde(default)]
    pub onnx_model_details: Vec<ModelVariantInfo>,
    #[serde(default)]
    pub scale_factors: Vec<u32>,
    #[serde(default)]
    pub fixed_scale_factor: Option<u32>,
    #[serde(default)]
    pub default_num_frames: Option<u32>,
    pub input_frame_mode: InputFrameMode,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckResult {
    pub ffmpeg: FfmpegInfo,
    pub gpu: GpuInfo,
    pub tensor_engines: TensorEngines,
    pub interpolation_algorithms: Vec<AlgorithmInfo>,
    pub super_resolution_algorithms: Vec<AlgorithmInfo>,
    pub runtime_mode: RuntimeMode,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckPayload {
    pub result: EnvironmentCheckResult,
    pub source: EnvironmentCheckSource,
    pub checked_at: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn environment_result_serializes_only_consumed_fields() {
        let raw = json!({
            "type": "check",
            "ffmpeg": {
                "available": true,
                "version": "7.0",
                "path": "ffmpeg",
                "ffprobePath": "ffprobe",
                "hwaccels": [],
                "encoderProfiles": [],
                "decoderProfiles": []
            },
            "gpu": {
                "available": false,
                "devices": [],
                "adapters": [{
                    "name": "GPU",
                    "vendor": "nvidia"
                }],
                "cudaAvailable": false
            },
            "tensorBackends": { "pytorch": true, "paddle": false, "onnx": true },
            "tensorEngines": { "pytorch": ["cuda"], "onnx": ["cuda"] },
            "onnxRuntime": { "available": true, "providers": ["CUDAExecutionProvider"] },
            "rifeModel": { "available": true, "version": "4.25", "path": "model" },
            "interpolationAlgorithms": [],
            "superResolutionAlgorithms": [],
            "animeProfiles": ["clean-lines"],
            "runtime": { "mode": "bundled" },
            "resources": { "runtimeRoot": "runtime" },
            "runtimeMode": "bundled"
        });

        let result: EnvironmentCheckResult =
            serde_json::from_value(raw).expect("environment result");
        let serialized = serde_json::to_value(result).expect("serialize result");
        let mut keys = serialized
            .as_object()
            .expect("object")
            .keys()
            .cloned()
            .collect::<Vec<_>>();
        keys.sort();

        assert_eq!(
            keys,
            vec![
                "ffmpeg",
                "gpu",
                "interpolationAlgorithms",
                "runtimeMode",
                "superResolutionAlgorithms",
                "tensorEngines",
            ]
        );
        assert_eq!(
            serialized["gpu"]["adapters"],
            json!([{"name": "GPU", "vendor": "nvidia"}])
        );
        assert_eq!(serialized["tensorEngines"]["paddle"], json!([]));
    }
}
