use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

use crate::models::config::JsonMap;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct FfmpegInfo {
    #[serde(default)]
    pub available: Option<bool>,
    #[serde(default)]
    pub version: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub ffprobe_path: Option<String>,
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
    pub available: Option<bool>,
    #[serde(default)]
    pub devices: Vec<String>,
    #[serde(default)]
    #[ts(type = "Record<string, unknown>[]")]
    pub adapters: Vec<JsonMap>,
    #[serde(default)]
    pub cuda_available: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TensorBackends {
    #[serde(default)]
    pub pytorch: Option<bool>,
    #[serde(default)]
    pub paddle: Option<bool>,
    #[serde(default)]
    pub onnx: Option<bool>,
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
pub struct OnnxRuntimeInfo {
    #[serde(default)]
    pub available: Option<bool>,
    #[serde(default)]
    pub providers: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct RifeModel {
    #[serde(default)]
    pub available: Option<bool>,
    #[serde(default)]
    pub version: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct RuntimeInfo {
    #[serde(default)]
    pub mode: Option<String>,
    #[serde(default)]
    pub bundled: Option<bool>,
    #[serde(default)]
    pub python_executable: Option<String>,
    #[serde(default)]
    pub default_model_available: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct AlgorithmInfo {
    pub name: String,
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
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckResult {
    #[serde(rename = "type")]
    pub kind: String,
    pub ffmpeg: FfmpegInfo,
    pub gpu: GpuInfo,
    pub tensor_backends: TensorBackends,
    #[serde(default)]
    pub tensor_engines: Option<TensorEngines>,
    #[serde(default)]
    pub backend_device_support: Option<BackendDeviceSupport>,
    #[serde(default)]
    pub onnx_runtime: Option<OnnxRuntimeInfo>,
    pub rife_model: RifeModel,
    #[serde(default)]
    pub interpolation_algorithms: Option<Vec<AlgorithmInfo>>,
    #[serde(default)]
    pub super_resolution_algorithms: Option<Vec<AlgorithmInfo>>,
    #[serde(default)]
    pub anime_profiles: Option<Vec<String>>,
    #[serde(default)]
    pub runtime: Option<RuntimeInfo>,
    #[serde(default)]
    pub resources: Option<JsonMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct EnvironmentCheckPayload {
    pub result: EnvironmentCheckResult,
    pub source: String,
    pub checked_at: String,
}
