use std::env;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Manager, Runtime};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;
use tokio::fs;

use crate::error::ShellError;
use crate::models::WorkbenchPreset;
use crate::runtime::ResolvedRuntimePaths;

// Schema 12 replaces compatibility-derived environment data with the strict,
// generated capability protocol. Older cache entries must be re-probed.
const ENVIRONMENT_CACHE_SCHEMA_VERSION: u32 = 12;
const WORKBENCH_PRESET_SCHEMA_VERSION: u32 = 1;
const ENVIRONMENT_CACHE_FILE: &str = "environment-cache.json";
const WORKBENCH_PRESET_FILE: &str = "workbench-preset.json";
const DEFAULT_RIFE_MODEL_VERSION: &str = "4.25";

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct EnvironmentCacheEntry {
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

/// 解析并创建应用本地数据目录。
///
/// Phase C.2.2:从 ``std::fs::create_dir_all`` 改为 ``tokio::fs``,避免
/// ``#[tauri::command] async fn`` 在 tokio runtime 上阻塞。
pub async fn app_data_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, ShellError> {
    let dir = env::var_os("VP_APP_DATA_DIR")
        .map(PathBuf::from)
        .map(Ok)
        .unwrap_or_else(|| {
            app.path().app_local_data_dir().map_err(|error| {
                ShellError::Persistence(format!("Unable to resolve app data directory: {error}"))
            })
        })?;
    fs::create_dir_all(&dir).await.map_err(|error| {
        ShellError::Persistence(format!(
            "Unable to create app data directory {}: {error}",
            dir.display()
        ))
    })?;
    Ok(dir)
}

fn environment_cache_path(base_dir: &Path) -> PathBuf {
    base_dir.join(ENVIRONMENT_CACHE_FILE)
}

fn workbench_preset_path(base_dir: &Path) -> PathBuf {
    base_dir.join(WORKBENCH_PRESET_FILE)
}

pub fn current_timestamp() -> Result<String, ShellError> {
    OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .map_err(|error| ShellError::Persistence(format!("Unable to format timestamp: {error}")))
}

/// 构造环境检查的指纹字符串,用于决定缓存命中。
///
/// 内部对 ffmpeg / ffprobe / model 等路径做 metadata stat,所以也是 async。
pub async fn build_environment_fingerprint(
    paths: &ResolvedRuntimePaths,
) -> Result<String, ShellError> {
    let model_version = env::var("VP_RIFE_MODEL_VERSION")
        .unwrap_or_else(|_| DEFAULT_RIFE_MODEL_VERSION.to_string());
    let default_model_path = paths
        .model_dir
        .as_ref()
        .map(|path| path.join(format!("flownet_v{model_version}.pkl")));
    serde_json::to_string(&json!({
        "host": resolve_host_identifier(),
        "backendDir": paths.backend_dir.to_string_lossy().to_string(),
        "runtimeRoot": paths.runtime_root.as_ref().map(|path| path.to_string_lossy().to_string()),
        "pythonExecutable": describe_path(Some(paths.python_executable.as_path())).await,
        "ffmpeg": describe_path(paths.ffmpeg_path.as_deref()).await,
        "ffprobe": describe_path(paths.ffprobe_path.as_deref()).await,
        "modelDir": describe_path(paths.model_dir.as_deref()).await,
        "defaultModel": describe_path(default_model_path.as_deref()).await,
        "modelVersion": model_version,
    }))
    .map_err(ShellError::from)
}

pub(crate) async fn load_environment_cache(
    base_dir: &Path,
    fingerprint: &str,
    force_refresh: bool,
) -> Option<(String, Value)> {
    if force_refresh {
        return None;
    }

    let raw = fs::read_to_string(environment_cache_path(base_dir))
        .await
        .ok()?;
    let entry = serde_json::from_str::<EnvironmentCacheEntry>(&raw).ok()?;
    if entry.schema_version != ENVIRONMENT_CACHE_SCHEMA_VERSION {
        return None;
    }
    if entry.fingerprint != fingerprint {
        return None;
    }
    Some((entry.checked_at, entry.result))
}

/// 原子地把序列化结果写入文件。
///
/// ``tempfile::NamedTempFile::persist`` 在所有平台上都是同步 syscall(Windows 走
/// ``MoveFileEx``,POSIX 走 ``rename``),Phase C.2.2 把这一段包到
/// ``tokio::task::spawn_blocking`` 避免阻塞 tokio worker。
///
/// Phase D.3.7 — Windows 上 OneDrive / 其它云盘代理偶尔会让 ``persist`` 拿
/// 到 ``Access Denied``。我们退到 ``%TEMP%/vp-workbench/<basename>``,用同样
/// 的原子写入语义重试一次。fallback 触发时 ``eprintln!`` 记一条 breadcrumb,
/// 避免静默吞掉问题(Tauri 没法在 storage 层直接 emit ``task-log``,因为
/// AppHandle 没参数到这里;若未来 caller 需要可视化,可以把
/// ``actual_path`` 返回出去)。
async fn atomic_write_json<T>(path: &Path, value: &T) -> Result<(), ShellError>
where
    T: Serialize,
{
    let data = serde_json::to_vec_pretty(value)?;
    match atomic_write_bytes(path, &data).await {
        Ok(()) => Ok(()),
        Err(primary_error) => {
            let fallback_path = fallback_persistence_path(path);
            if fallback_path == path {
                // No usable fallback location — propagate the original error.
                return Err(primary_error);
            }
            match atomic_write_bytes(&fallback_path, &data).await {
                Ok(()) => {
                    eprintln!(
                        "VP Workbench persistence fell back to {} (primary {} failed: {})",
                        fallback_path.display(),
                        path.display(),
                        primary_error,
                    );
                    Ok(())
                }
                Err(_) => Err(primary_error),
            }
        }
    }
}

fn fallback_persistence_path(path: &Path) -> PathBuf {
    let basename = path
        .file_name()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("vp-workbench.json"));
    env::temp_dir().join("vp-workbench").join(basename)
}

async fn atomic_write_bytes(path: &Path, data: &[u8]) -> Result<(), ShellError> {
    let dir = path.parent().unwrap_or(Path::new(".")).to_path_buf();
    fs::create_dir_all(&dir).await.map_err(|error| {
        ShellError::Persistence(format!(
            "Unable to create directory {}: {error}",
            dir.display()
        ))
    })?;

    // 写到 ``<dir>/<uuid>.tmp`` 后原子 rename。两步都包成 spawn_blocking 来
    // 避免在 worker 线程内阻塞;persist() 本身没有 async 形式。
    let target = path.to_path_buf();
    let dir_for_blocking = dir.clone();
    let data = data.to_vec();
    tokio::task::spawn_blocking(move || -> Result<(), ShellError> {
        let mut temp = tempfile::NamedTempFile::new_in(&dir_for_blocking).map_err(|error| {
            ShellError::Persistence(format!(
                "Unable to create temp file in {}: {error}",
                dir_for_blocking.display()
            ))
        })?;
        std::io::Write::write_all(temp.as_file_mut(), &data).map_err(|error| {
            ShellError::Persistence(format!("Unable to write temp file: {error}"))
        })?;
        // flush 在 drop 时自动发生,这里显式调以便提前发现写失败。
        temp.as_file_mut().sync_all().map_err(|error| {
            ShellError::Persistence(format!("Unable to flush temp file: {error}"))
        })?;
        temp.persist(&target).map_err(|error| {
            ShellError::Persistence(format!(
                "Unable to persist file to {}: {}",
                target.display(),
                error.error
            ))
        })?;
        Ok(())
    })
    .await
    .map_err(|error| ShellError::Persistence(format!("Persistence task join failed: {error}")))??;

    Ok(())
}

pub async fn save_environment_cache(
    base_dir: &Path,
    checked_at: &str,
    fingerprint: &str,
    result: &Value,
) -> Result<(), ShellError> {
    let entry = EnvironmentCacheEntry {
        schema_version: ENVIRONMENT_CACHE_SCHEMA_VERSION,
        checked_at: checked_at.to_string(),
        fingerprint: fingerprint.to_string(),
        result: result.clone(),
    };
    atomic_write_json(&environment_cache_path(base_dir), &entry).await
}

pub async fn load_workbench_preset(base_dir: &Path) -> Option<WorkbenchPreset> {
    let raw = fs::read_to_string(workbench_preset_path(base_dir))
        .await
        .ok()?;
    let entry = serde_json::from_str::<WorkbenchPresetEntry>(&raw).ok()?;
    if entry.schema_version != WORKBENCH_PRESET_SCHEMA_VERSION {
        return None;
    }
    Some(entry.preset)
}

pub async fn save_workbench_preset(
    base_dir: &Path,
    preset: &WorkbenchPreset,
) -> Result<(), ShellError> {
    let entry = WorkbenchPresetEntry {
        schema_version: WORKBENCH_PRESET_SCHEMA_VERSION,
        preset: preset.clone(),
    };
    atomic_write_json(&workbench_preset_path(base_dir), &entry).await
}

fn resolve_host_identifier() -> String {
    env::var("COMPUTERNAME")
        .or_else(|_| env::var("HOSTNAME"))
        .unwrap_or_else(|_| "unknown-host".to_string())
}

async fn describe_path(path: Option<&Path>) -> Value {
    let Some(path) = path else {
        return Value::Null;
    };

    let mut object = serde_json::Map::new();
    object.insert(
        "path".to_string(),
        Value::String(path.to_string_lossy().to_string()),
    );

    match fs::metadata(path).await {
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
        build_environment_fingerprint, environment_cache_path, load_environment_cache,
        load_workbench_preset, save_environment_cache, save_workbench_preset,
        workbench_preset_path, EnvironmentCacheEntry, WorkbenchPresetEntry,
    };
    use crate::models::config::{
        DecodeConfig, DecodeMode, EncodeConfig, FpsMode, InterpolationConfig, OutputConfig,
        PostprocessConfig, PreprocessConfig, ProcessOrder, RateControlConfig, RateControlMode,
        SuperResolutionConfig, TensorBackend, WorkbenchPreset, WorkflowConfig,
    };
    use crate::runtime::ResolvedRuntimePaths;
    use serde_json::json;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::{env, fs};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    #[tokio::test]
    async fn environment_fingerprint_excludes_output_path_state() {
        let paths = ResolvedRuntimePaths {
            backend_dir: PathBuf::from("backend"),
            runtime_root: Some(PathBuf::from("runtime")),
            python_executable: PathBuf::from("python"),
            ffmpeg_path: Some(PathBuf::from("ffmpeg")),
            ffprobe_path: Some(PathBuf::from("ffprobe")),
            model_dir: Some(PathBuf::from("models")),
            tensorrt_dir: None,
            log_dir: PathBuf::from("logs"),
        };

        let encoded = build_environment_fingerprint(&paths)
            .await
            .expect("build fingerprint");
        let fingerprint: serde_json::Value =
            serde_json::from_str(&encoded).expect("parse fingerprint");

        assert!(fingerprint.get("outputDir").is_none());
        assert_eq!(fingerprint["backendDir"], "backend");
    }

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
                mode: DecodeMode::Hardware,
                hwaccel: Some("cuda".to_string()),
                hwaccel_device: Some("0".to_string()),
                decoder: Some("hevc_cuvid".to_string()),
                options: Default::default(),
            },
            workflow_config: WorkflowConfig {
                fps_mode: FpsMode::Target,
                process_order: ProcessOrder::SuperResolutionThenInterpolation,
                interpolation: InterpolationConfig {
                    enabled: true,
                    target_fps: 60.0,
                    multi: 2,
                    algorithm: "rife".to_string(),
                    model: "4.25".to_string(),
                    onnx_model: None,
                    scale: 1.0,
                    fp16: false,
                    tensor_backend: TensorBackend::Pytorch,
                    engine: "cuda".to_string(),
                },
                super_resolution: SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                    onnx_model: None,
                    tensor_backend: TensorBackend::Onnx,
                    engine: "cuda".to_string(),
                    num_frames: 10,
                },
                preprocess: PreprocessConfig {
                    enabled: false,
                    filters: Vec::new(),
                },
                postprocess: PostprocessConfig {
                    enabled: false,
                    filters: Vec::new(),
                },
            },
            encode_config: EncodeConfig {
                codec: "hevc_nvenc".to_string(),
                family: "nvidia".to_string(),
                container: "mp4".to_string(),
                keep_audio: true,
                rate_control: RateControlConfig {
                    mode: RateControlMode::Cq,
                    value: json!(23),
                },
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: Some("D:/output".to_string()),
                open_on_complete: true,
                segment_frames: 1000,
            },
        }
    }

    #[tokio::test]
    async fn reuses_valid_environment_cache() {
        let dir = temp_dir("env-hit");
        save_environment_cache(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &json!({"type":"check"}),
        )
        .await
        .expect("write env cache");

        let (checked_at, result) = load_environment_cache(&dir, "fingerprint-a", false)
            .await
            .expect("cache hit");
        assert_eq!(checked_at, "2026-04-23T11:00:00Z");
        assert_eq!(result["type"], "check");
    }

    #[tokio::test]
    async fn invalidates_environment_cache_when_fingerprint_changes() {
        let dir = temp_dir("env-fingerprint");
        save_environment_cache(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &json!({"type":"check"}),
        )
        .await
        .expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-b", false).await;
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn invalidates_environment_cache_with_schema_version_eleven() {
        let dir = temp_dir("env-schema-v11");
        let payload = serde_json::to_vec_pretty(&EnvironmentCacheEntry {
            schema_version: 11,
            checked_at: "2026-07-11T12:00:00Z".to_string(),
            fingerprint: "fingerprint-a".to_string(),
            result: json!({"type":"check", "runtimeMode":"bundled"}),
        })
        .expect("serialize env cache");
        fs::write(environment_cache_path(&dir), payload).expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", false).await;
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn ignores_damaged_environment_cache() {
        let dir = temp_dir("env-damaged");
        fs::write(environment_cache_path(&dir), "{not-json").expect("write invalid cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", false).await;
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn bypasses_environment_cache_when_force_refresh_is_enabled() {
        let dir = temp_dir("env-force-refresh");
        save_environment_cache(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &json!({"type":"check"}),
        )
        .await
        .expect("write env cache");

        let entry = load_environment_cache(&dir, "fingerprint-a", true).await;
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn loads_saved_workbench_preset() {
        let dir = temp_dir("preset");
        let preset = sample_preset();

        save_workbench_preset(&dir, &preset)
            .await
            .expect("save preset");

        let loaded = load_workbench_preset(&dir).await.expect("load preset");
        assert_eq!(loaded.decode_config.decoder.as_deref(), Some("hevc_cuvid"));
        assert_eq!(loaded.encode_config.codec, "hevc_nvenc");
    }

    #[tokio::test]
    async fn ignores_workbench_preset_with_unknown_schema_version() {
        let dir = temp_dir("preset-schema");
        let payload = serde_json::to_vec_pretty(&WorkbenchPresetEntry {
            schema_version: 999,
            preset: sample_preset(),
        })
        .expect("serialize preset");
        fs::write(workbench_preset_path(&dir), payload).expect("write preset");

        let loaded = load_workbench_preset(&dir).await;
        assert!(loaded.is_none());
    }
}
