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
        pub(crate) enum $name {
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
pub(crate) enum RuntimeMode {
    External,
    Bundled,
    ExpectedBundled,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct CapabilityChoice {
    pub(crate) label: String,
    #[ts(type = "string | number | boolean")]
    pub(crate) value: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct CapabilityOptionSpec {
    pub(crate) name: String,
    pub(crate) label: String,
    pub(crate) r#type: CapabilityOptionKind,
    #[ts(type = "string | number | boolean | null")]
    pub(crate) default_value: Value,
    #[serde(default)]
    pub(crate) choices: Vec<CapabilityChoice>,
    #[serde(default)]
    pub(crate) min: Option<f64>,
    #[serde(default)]
    pub(crate) max: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct RateControlModeSpec {
    pub(crate) mode: RateControlMode,
    pub(crate) label: String,
    #[ts(type = "string | number")]
    pub(crate) default_value: Value,
    pub(crate) unit: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct HardwareDeviceOptionSpec {
    pub(crate) value: String,
    pub(crate) label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct CodecProfileSpec {
    pub(crate) name: String,
    pub(crate) label: String,
    pub(crate) family: CodecProfileFamily,
    pub(crate) codec: String,
    pub(crate) available: bool,
    #[serde(default)]
    pub(crate) hardware_devices: Vec<String>,
    #[serde(default)]
    pub(crate) options: Vec<CapabilityOptionSpec>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    pub(crate) rate_control_modes: Option<Vec<RateControlModeSpec>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    pub(crate) hardware_device_options: Option<HashMap<String, Vec<HardwareDeviceOptionSpec>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct GpuAdapter {
    pub(crate) name: String,
    pub(crate) vendor: GpuVendor,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct FfmpegInfo {
    pub(crate) available: bool,
    #[serde(default)]
    pub(crate) hwaccels: Vec<String>,
    #[serde(default)]
    pub(crate) encoder_profiles: Vec<CodecProfileSpec>,
    #[serde(default)]
    pub(crate) decoder_profiles: Vec<CodecProfileSpec>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct GpuInfo {
    #[serde(default)]
    pub(crate) adapters: Vec<GpuAdapter>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct TensorEngines {
    #[serde(default)]
    pub(crate) pytorch: Vec<InferenceEngine>,
    #[serde(default)]
    pub(crate) paddle: Vec<InferenceEngine>,
    #[serde(default)]
    pub(crate) onnx: Vec<InferenceEngine>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct ModelEngineMetricInfo {
    #[serde(default)]
    pub(crate) gflops_per_megapixel: Option<f64>,
    #[serde(default)]
    pub(crate) activation_bytes_per_megapixel: Option<f64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub(crate) runtime_overhead_bytes: Option<u64>,
    #[serde(default)]
    pub(crate) runtime_frame_count: Option<u32>,
    #[serde(default)]
    pub(crate) input_modulo: Option<u32>,
    #[serde(default)]
    pub(crate) analysis_status: String,
    #[serde(default)]
    pub(crate) analysis_notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct ModelMetricInfo {
    #[serde(default)]
    #[ts(type = "number | null")]
    pub(crate) parameter_count: Option<u64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub(crate) parameter_bytes: Option<u64>,
    #[serde(default)]
    pub(crate) gflops_per_megapixel: Option<f64>,
    #[serde(default)]
    pub(crate) activation_bytes_per_megapixel: Option<f64>,
    #[serde(default)]
    #[ts(type = "number | null")]
    pub(crate) runtime_overhead_bytes: Option<u64>,
    #[serde(default)]
    pub(crate) runtime_frame_count: Option<u32>,
    #[serde(default)]
    pub(crate) input_modulo: Option<u32>,
    #[serde(default)]
    pub(crate) analysis_status: String,
    #[serde(default)]
    pub(crate) analysis_notes: Vec<String>,
    #[serde(default)]
    pub(crate) engine_metrics: HashMap<String, ModelEngineMetricInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct ModelVariantInfo {
    pub(crate) name: String,
    pub(crate) label: String,
    pub(crate) metrics: ModelMetricInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct AlgorithmInfo {
    pub(crate) name: String,
    pub(crate) family: AlgorithmFamily,
    #[serde(default)]
    pub(crate) tensor_backends: Vec<TensorBackend>,
    pub(crate) models: Vec<String>,
    #[serde(default)]
    pub(crate) onnx_models: Vec<String>,
    #[serde(default)]
    pub(crate) model_details: Vec<ModelVariantInfo>,
    #[serde(default)]
    pub(crate) onnx_model_details: Vec<ModelVariantInfo>,
    #[serde(default)]
    pub(crate) scale_factors: Vec<u32>,
    #[serde(default)]
    pub(crate) fixed_scale_factor: Option<u32>,
    #[serde(default)]
    pub(crate) default_num_frames: Option<u32>,
    pub(crate) input_frame_mode: InputFrameMode,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct EnvironmentCheckResult {
    pub(crate) ffmpeg: FfmpegInfo,
    pub(crate) gpu: GpuInfo,
    pub(crate) tensor_engines: TensorEngines,
    pub(crate) interpolation_algorithms: Vec<AlgorithmInfo>,
    pub(crate) super_resolution_algorithms: Vec<AlgorithmInfo>,
    pub(crate) runtime_mode: RuntimeMode,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub(crate) struct EnvironmentCheckPayload {
    pub(crate) result: EnvironmentCheckResult,
    pub(crate) source: EnvironmentCheckSource,
    pub(crate) checked_at: String,
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
