use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tauri::{AppHandle, Manager, Runtime};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

use crate::models::WorkbenchPreset;
use crate::runtime::ResolvedRuntimePaths;

const ENVIRONMENT_CACHE_SCHEMA_VERSION: u32 = 1;
const WORKBENCH_PRESET_SCHEMA_VERSION: u32 = 1;
const ENVIRONMENT_CACHE_FILE: &str = "environment-cache.json";
const WORKBENCH_PRESET_FILE: &str = "workbench-preset.json";
const DEFAULT_RIFE_MODEL_VERSION: &str = "4.25";

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EnvironmentCacheEntry {
    pub schema_version: u32,
    pub checked_at: String,
    pub fingerprint: String,
    pub result: Value,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct WorkbenchPresetEntry {
    pub schema_version: u32,
    pub preset: WorkbenchPreset,
}

pub fn app_data_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_local_data_dir()
        .map_err(|error| format!("Unable to resolve app data directory: {error}"))?;
    fs::create_dir_all(&dir)
        .map_err(|error| format!("Unable to create app data directory {}: {error}", dir.display()))?;
    Ok(dir)
}

pub fn environment_cache_path(base_dir: &Path) -> PathBuf {
    base_dir.join(ENVIRONMENT_CACHE_FILE)
}

pub fn workbench_preset_path(base_dir: &Path) -> PathBuf {
    base_dir.join(WORKBENCH_PRESET_FILE)
}

pub fn current_timestamp() -> Result<String, String> {
    OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .map_err(|error| format!("Unable to format timestamp: {error}"))
}

pub fn build_environment_fingerprint(paths: &ResolvedRuntimePaths) -> Result<String, String> {
    let model_version = env::var("VP_RIFE_MODEL_VERSION").unwrap_or_else(|_| DEFAULT_RIFE_MODEL_VERSION.to_string());
    let default_model_path = paths
        .model_dir
        .as_ref()
        .map(|path| path.join(format!("flownet_v{model_version}.pkl")));
    serde_json::to_string(&json!({
        "host": resolve_host_identifier(),
        "backendDir": paths.backend_dir.to_string_lossy().to_string(),
        "runtimeRoot": paths.runtime_root.as_ref().map(|path| path.to_string_lossy().to_string()),
        "outputDir": paths.output_dir.to_string_lossy().to_string(),
        "pythonExecutable": describe_path(Some(paths.python_executable.as_path())),
        "ffmpeg": describe_path(paths.ffmpeg_path.as_deref()),
        "ffprobe": describe_path(paths.ffprobe_path.as_deref()),
        "modelDir": describe_path(paths.model_dir.as_deref()),
        "defaultModel": describe_path(default_model_path.as_deref()),
        "modelVersion": model_version,
    }))
    .map_err(|error| format!("Unable to serialize environment fingerprint: {error}"))
}

pub fn load_environment_cache(
    base_dir: &Path,
    fingerprint: &str,
    force_refresh: bool,
) -> Option<EnvironmentCacheEntry> {
    if force_refresh {
        return None;
    }

    let raw = fs::read_to_string(environment_cache_path(base_dir)).ok()?;
    let entry = serde_json::from_str::<EnvironmentCacheEntry>(&raw).ok()?;
    if entry.schema_version != ENVIRONMENT_CACHE_SCHEMA_VERSION {
        return None;
    }
    if entry.fingerprint != fingerprint {
        return None;
    }
    Some(entry)
}

pub fn save_environment_cache(
    base_dir: &Path,
    checked_at: &str,
    fingerprint: &str,
    result: &Value,
) -> Result<(), String> {
    fs::create_dir_all(base_dir)
        .map_err(|error| format!("Unable to create environment cache directory {}: {error}", base_dir.display()))?;
    let entry = EnvironmentCacheEntry {
        schema_version: ENVIRONMENT_CACHE_SCHEMA_VERSION,
        checked_at: checked_at.to_string(),
        fingerprint: fingerprint.to_string(),
        result: result.clone(),
    };
    let payload = serde_json::to_vec_pretty(&entry)
        .map_err(|error| format!("Unable to serialize environment cache entry: {error}"))?;
    fs::write(environment_cache_path(base_dir), payload)
        .map_err(|error| format!("Unable to write environment cache: {error}"))
}

pub fn load_workbench_preset(base_dir: &Path) -> Option<WorkbenchPreset> {
    let raw = fs::read_to_string(workbench_preset_path(base_dir)).ok()?;
    let entry = serde_json::from_str::<WorkbenchPresetEntry>(&raw).ok()?;
    if entry.schema_version != WORKBENCH_PRESET_SCHEMA_VERSION {
        return None;
    }
    Some(entry.preset)
}

pub fn save_workbench_preset(base_dir: &Path, preset: &WorkbenchPreset) -> Result<(), String> {
    fs::create_dir_all(base_dir)
        .map_err(|error| format!("Unable to create preset directory {}: {error}", base_dir.display()))?;
    let entry = WorkbenchPresetEntry {
        schema_version: WORKBENCH_PRESET_SCHEMA_VERSION,
        preset: preset.clone(),
    };
    let payload = serde_json::to_vec_pretty(&entry)
        .map_err(|error| format!("Unable to serialize workbench preset: {error}"))?;
    fs::write(workbench_preset_path(base_dir), payload)
        .map_err(|error| format!("Unable to write workbench preset: {error}"))
}

fn resolve_host_identifier() -> String {
    env::var("COMPUTERNAME")
        .or_else(|_| env::var("HOSTNAME"))
        .unwrap_or_else(|_| "unknown-host".to_string())
}

fn describe_path(path: Option<&Path>) -> Value {
    let Some(path) = path else {
        return Value::Null;
    };

    let mut object = serde_json::Map::new();
    object.insert(
        "path".to_string(),
        Value::String(path.to_string_lossy().to_string()),
    );

    match fs::metadata(path) {
        Ok(metadata) => {
            object.insert("exists".to_string(), Value::Bool(true));
            object.insert("size".to_string(), Value::from(metadata.len()));
            object.insert("isFile".to_string(), Value::Bool(metadata.is_file()));
            object.insert("isDir".to_string(), Value::Bool(metadata.is_dir()));
            object.insert(
                "modified".to_string(),
                metadata
                    .modified()
                    .ok()
                    .and_then(|value| value.duration_since(UNIX_EPOCH).ok())
                    .map(|value| Value::from(value.as_secs()))
                    .unwrap_or(Value::Null),
            );
        }
        Err(_) => {
            object.insert("exists".to_string(), Value::Bool(false));
        }
    }

    Value::Object(object)
}

#[cfg(test)]
mod tests {
    use super::{
        WorkbenchPresetEntry, environment_cache_path, load_environment_cache, load_workbench_preset,
        save_environment_cache, save_workbench_preset, workbench_preset_path,
    };
    use crate::models::{
        AnimeConfig, DecodeConfig, EncodeConfig, InterpolationConfig, OutputConfig, RateControlConfig,
        WorkbenchPreset, WorkflowConfig,
    };
    use serde_json::json;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::{env, fs};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    fn temp_dir(label: &str) -> PathBuf {
        let dir = env::temp_dir().join(format!(
            "vp-workbench-{label}-{}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        if dir.exists() {
            let _ = fs::remove_dir_all(&dir);
        }
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    fn sample_preset() -> WorkbenchPreset {
        WorkbenchPreset {
            decode_config: DecodeConfig {
                mode: "hardware".to_string(),
                hwaccel: Some("cuda".to_string()),
                hwaccel_device: Some("0".to_string()),
                decoder: Some("hevc_cuvid".to_string()),
                options: Default::default(),
            },
            workflow_config: WorkflowConfig {
                fps_mode: "target".to_string(),
                process_order: "super_resolution_then_interpolation".to_string(),
                interpolation: InterpolationConfig {
                    enabled: true,
                    target_fps: 60.0,
                    multi: 2,
                    model: "4.25".to_string(),
                    scale: 1.0,
                    fp16: false,
                    tensor_backend: "pytorch".to_string(),
                },
                super_resolution: crate::models::SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                },
                anime: AnimeConfig {
                    enabled: false,
                    profile: "clean-lines".to_string(),
                    denoise: 10,
                    edge_boost: 15,
                },
            },
            encode_config: EncodeConfig {
                codec: "hevc_nvenc".to_string(),
                family: "nvidia".to_string(),
                container: "mp4".to_string(),
                keep_audio: true,
                rate_control: RateControlConfig {
                    mode: "cq".to_string(),
                    value: json!(23),
                },
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: "D:/output".to_string(),
                open_on_complete: true,
                segment_frames: 1000,
            },
        }
    }

    #[test]
    fn reuses_valid_environment_cache() {
        let dir = temp_dir("env-hit");
        save_environment_cache(&dir, "2026-04-23T11:00:00Z", "fingerprint-a", &json!({"type":"check"}))
            .expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", false).expect("cache hit");
        assert_eq!(entry.checked_at, "2026-04-23T11:00:00Z");
        assert_eq!(entry.result["type"], "check");
    }

    #[test]
    fn invalidates_environment_cache_when_fingerprint_changes() {
        let dir = temp_dir("env-fingerprint");
        save_environment_cache(&dir, "2026-04-23T11:00:00Z", "fingerprint-a", &json!({"type":"check"}))
            .expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-b", false);
        assert!(entry.is_none());
    }

    #[test]
    fn ignores_damaged_environment_cache() {
        let dir = temp_dir("env-damaged");
        fs::write(environment_cache_path(&dir), "{not-json").expect("write invalid cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", false);
        assert!(entry.is_none());
    }

    #[test]
    fn bypasses_environment_cache_when_force_refresh_is_enabled() {
        let dir = temp_dir("env-force-refresh");
        save_environment_cache(&dir, "2026-04-23T11:00:00Z", "fingerprint-a", &json!({"type":"check"}))
            .expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", true);
        assert!(entry.is_none());
    }

    #[test]
    fn loads_saved_workbench_preset() {
        let dir = temp_dir("preset");
        let preset = sample_preset();

        save_workbench_preset(&dir, &preset).expect("save preset");

        let loaded = load_workbench_preset(&dir).expect("load preset");
        assert_eq!(loaded.decode_config.decoder.as_deref(), Some("hevc_cuvid"));
        assert_eq!(loaded.encode_config.codec, "hevc_nvenc");
    }

    #[test]
    fn ignores_workbench_preset_with_unknown_schema_version() {
        let dir = temp_dir("preset-schema");
        let payload = serde_json::to_vec_pretty(&WorkbenchPresetEntry {
            schema_version: 999,
            preset: sample_preset(),
        })
        .expect("serialize preset");
        fs::write(workbench_preset_path(&dir), payload).expect("write preset");

        let loaded = load_workbench_preset(&dir);
        assert!(loaded.is_none());
    }
}
