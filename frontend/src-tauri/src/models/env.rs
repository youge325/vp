use std::collections::HashMap;

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

use crate::models::config::JsonMap;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct FfmpegInfo {
    pub available: bool,
    #[serde(default)]
    pub hwaccels: Vec<String>,
    #[serde(default)]
    #[ts(type = "Record<string, unknown>[]")]
    pub encoder_profiles: Vec<JsonMap>,
    #[serde(default)]
    #[ts(type = "Record<string, unknown>[]")]
    pub decoder_profiles: Vec<JsonMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct GpuInfo {
    #[serde(default)]
    #[ts(type = "Record<string, unknown>[]")]
    pub adapters: Vec<JsonMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TensorEngines {
    #[serde(default)]
    pub pytorch: Option<Vec<String>>,
    #[serde(default)]
    pub paddle: Option<Vec<String>>,
    #[serde(default)]
    pub onnx: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct BackendDeviceSupport {
    #[serde(default)]
    pub pytorch: Option<Vec<String>>,
    #[serde(default)]
    pub paddle: Option<Vec<String>>,
    #[serde(default)]
    pub onnx: Option<Vec<String>>,
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
    pub parameter_count: Option<u64>,
    #[serde(default)]
    pub parameter_bytes: Option<u64>,
    #[serde(default)]
    pub gflops_per_megapixel: Option<f64>,
    #[serde(default)]
    pub activation_bytes_per_megapixel: Option<f64>,
    #[serde(default)]
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
    #[serde(default)]
    pub family: Option<String>,
    /// Phase 8 — tensor backends this algorithm has a working
    /// implementation for. The frontend uses this list to hide the
    /// algorithm from the dropdown when the currently selected
    /// ``workflow.interpolation.tensorBackend`` is not a member —
    /// previously every algorithm showed up under every backend
    /// because the metadata had no such field.
    ///
    /// Wire values match ``tensor_backend.py::get_tensor_backend``
    /// (``"pytorch"`` / ``"paddle"`` / ``"onnx"``). Modelled as
    /// ``Vec<String>`` (not a dedicated enum) because the Python side
    /// already speaks these strings end-to-end and the schema-drift
    /// gate would otherwise need a third enum to police.
    ///
    /// ``#[serde(default)]`` keeps old persisted ``EnvironmentCheckCache``
    /// entries (which predate this field) deserializable; they fall back
    /// to an empty vec, which the frontend filter treats as "do not
    /// show under any backend" — safer than silently showing under all.
    #[serde(default)]
    pub tensor_backends: Vec<String>,
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
    #[serde(default)]
    pub sequence_mode: Option<String>,
    #[serde(default)]
    pub input_frame_mode: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckResult {
    pub ffmpeg: FfmpegInfo,
    pub gpu: GpuInfo,
    pub tensor_engines: TensorEngines,
    pub backend_device_support: BackendDeviceSupport,
    pub interpolation_algorithms: Vec<AlgorithmInfo>,
    pub super_resolution_algorithms: Vec<AlgorithmInfo>,
    pub runtime_mode: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckPayload {
    pub result: EnvironmentCheckResult,
    pub source: String,
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
            "gpu": { "available": false, "devices": [], "adapters": [], "cudaAvailable": false },
            "tensorBackends": { "pytorch": true, "paddle": false, "onnx": true },
            "tensorEngines": { "pytorch": ["cuda"], "onnx": ["cuda"] },
            "backendDeviceSupport": { "pytorch": ["nvidia"], "onnx": ["nvidia"] },
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
                "backendDeviceSupport",
                "ffmpeg",
                "gpu",
                "interpolationAlgorithms",
                "runtimeMode",
                "superResolutionAlgorithms",
                "tensorEngines",
            ]
        );
    }
}
