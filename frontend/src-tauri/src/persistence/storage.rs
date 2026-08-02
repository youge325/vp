use std::env;
use std::fmt;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::UNIX_EPOCH;

use chrono::{SecondsFormat, Utc};
use serde::Serialize;
use serde_json::{json, Value};
use tokio::fs;

use crate::error::ShellError;
use crate::generated::{ENVIRONMENT_CACHE_SCHEMA_VERSION, WORKBENCH_PRESET_SCHEMA_VERSION};
use crate::models::{
    EnvironmentCacheEntry, EnvironmentCheckPayload, EnvironmentCheckResult, EnvironmentCheckSource,
    WorkbenchPreset, WorkbenchPresetEntry,
};
use crate::persistence::transaction::PathTransactions;
use crate::runtime::ResolvedRuntimePaths;

const ENVIRONMENT_CACHE_FILE: &str = "environment-cache.json";
const WORKBENCH_PRESET_FILE: &str = "workbench-preset.json";
static QUARANTINE_SEQUENCE: AtomicU64 = AtomicU64::new(0);

#[derive(Clone, PartialEq, Eq)]
struct EnvironmentFlightKey {
    fingerprint: String,
    force_refresh: bool,
}

#[derive(Clone, Copy, PartialEq, Eq)]
struct PresetFlightKey;

#[derive(Clone)]
enum PresetLoadOutcome {
    Missing,
    Found(Box<WorkbenchPreset>),
    Invalid(String),
}

static ENVIRONMENT_TRANSACTIONS: PathTransactions<EnvironmentFlightKey, EnvironmentCheckPayload> =
    PathTransactions::new();
static PRESET_TRANSACTIONS: PathTransactions<PresetFlightKey, PresetLoadOutcome> =
    PathTransactions::new();

enum QuarantineReason {
    Corrupt,
    InvalidVersion,
    Version(u64),
}

impl QuarantineReason {
    fn from_version(value: &Value) -> Self {
        value
            .as_u64()
            .map(Self::Version)
            .unwrap_or(Self::InvalidVersion)
    }
}

impl fmt::Display for QuarantineReason {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Corrupt => formatter.write_str("corrupt"),
            Self::InvalidVersion => formatter.write_str("corrupt-version"),
            Self::Version(version) => write!(formatter, "v{version}"),
        }
    }
}

fn environment_cache_path(base_dir: &Path) -> PathBuf {
    base_dir.join(ENVIRONMENT_CACHE_FILE)
}

fn workbench_preset_path(base_dir: &Path) -> PathBuf {
    base_dir.join(WORKBENCH_PRESET_FILE)
}

async fn read_optional_bytes(
    path: &Path,
    description: &str,
) -> Result<Option<Vec<u8>>, ShellError> {
    match fs::read(path).await {
        Ok(raw) => Ok(Some(raw)),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(ShellError::Persistence(format!(
            "Unable to read {description} {}: {error}",
            path.display()
        ))),
    }
}

fn current_timestamp() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}

/// 构造环境检查的指纹字符串,用于决定缓存命中。
///
/// 内部对 ffmpeg / ffprobe / model 等路径做 metadata stat,所以也是 async。
pub(crate) async fn build_environment_fingerprint(
    paths: &ResolvedRuntimePaths,
) -> Result<String, ShellError> {
    let default_model_path = paths
        .model_dir
        .as_ref()
        .map(|path| path.join(format!("flownet_v{}.pkl", paths.rife_model_version)));
    serde_json::to_string(&json!({
        "host": resolve_host_identifier(),
        "backendDir": paths.backend_dir.to_string_lossy().to_string(),
        "runtimeRoot": paths.runtime_root.as_ref().map(|path| path.to_string_lossy().to_string()),
        "pythonExecutable": describe_path(Some(paths.python_executable.as_path())).await,
        "ffmpeg": describe_path(paths.ffmpeg_path.as_deref()).await,
        "ffprobe": describe_path(paths.ffprobe_path.as_deref()).await,
        "modelDir": describe_path(paths.model_dir.as_deref()).await,
        "defaultModel": describe_path(default_model_path.as_deref()).await,
        "modelVersion": paths.rife_model_version,
        "tensorrtDir": describe_path(paths.tensorrt_dir.as_deref()).await,
    }))
    .map_err(|error| {
        ShellError::SchemaValidation(format!("Unable to encode environment fingerprint: {error}"))
    })
}

async fn load_environment_cache_entry(
    path: &Path,
    fingerprint: &str,
    force_refresh: bool,
) -> Result<Option<(String, EnvironmentCheckResult)>, ShellError> {
    if force_refresh {
        return Ok(None);
    }

    let Some(raw) = read_optional_bytes(path, "environment cache").await? else {
        return Ok(None);
    };
    let entry = match serde_json::from_slice::<EnvironmentCacheEntry>(&raw) {
        Ok(entry) => entry,
        Err(_) => {
            quarantine_file(path, QuarantineReason::Corrupt).await?;
            return Ok(None);
        }
    };
    if entry.schema_version != ENVIRONMENT_CACHE_SCHEMA_VERSION {
        quarantine_file(path, QuarantineReason::from_version(&entry.schema_version)).await?;
        return Ok(None);
    }
    if entry.fingerprint.to_string() != fingerprint {
        return Ok(None);
    }
    Ok(Some((
        entry.checked_at.to_rfc3339_opts(SecondsFormat::Secs, true),
        entry.result,
    )))
}

pub(crate) async fn resolve_environment_cache<F, Fut>(
    base_dir: &Path,
    fingerprint: &str,
    force_refresh: bool,
    probe: F,
) -> Result<EnvironmentCheckPayload, ShellError>
where
    F: FnOnce() -> Fut,
    Fut: Future<Output = Result<EnvironmentCheckResult, ShellError>>,
{
    let path = environment_cache_path(base_dir);
    let key = EnvironmentFlightKey {
        fingerprint: fingerprint.to_string(),
        force_refresh,
    };
    ENVIRONMENT_TRANSACTIONS
        .run(&path, key, || async {
            if let Some((checked_at, result)) =
                load_environment_cache_entry(&path, fingerprint, force_refresh).await?
            {
                return Ok(EnvironmentCheckPayload {
                    result,
                    source: EnvironmentCheckSource::Cache,
                    checked_at,
                });
            }

            let result = probe().await?;
            let checked_at = current_timestamp();
            save_environment_cache_entry(&path, &checked_at, fingerprint, &result).await?;
            Ok(EnvironmentCheckPayload {
                result,
                source: EnvironmentCheckSource::Probe,
                checked_at,
            })
        })
        .await
}

/// 原子地把序列化结果写入文件。
///
/// ``tempfile::NamedTempFile::persist`` 是同步 syscall，因此在 blocking
/// worker 中执行，避免阻塞 Tokio worker。
///
async fn atomic_write_json<T>(path: &Path, value: &T) -> Result<(), ShellError>
where
    T: Serialize,
{
    let data = serde_json::to_vec_pretty(value).map_err(|error| {
        ShellError::Persistence(format!(
            "Unable to serialize persistence payload for {}: {error}",
            path.display()
        ))
    })?;
    atomic_write_bytes(path, &data).await
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

async fn save_environment_cache_entry(
    path: &Path,
    checked_at: &str,
    fingerprint: &str,
    result: &EnvironmentCheckResult,
) -> Result<(), ShellError> {
    let entry = serde_json::from_value::<EnvironmentCacheEntry>(json!({
        "schemaVersion": ENVIRONMENT_CACHE_SCHEMA_VERSION,
        "checkedAt": checked_at,
        "fingerprint": fingerprint,
        "result": result,
    }))
    .map_err(|error| {
        ShellError::SchemaValidation(format!(
            "Unable to construct environment cache contract: {error}"
        ))
    })?;
    atomic_write_json(path, &entry).await
}

pub(crate) async fn load_workbench_preset(
    base_dir: &Path,
) -> Result<Option<WorkbenchPreset>, ShellError> {
    let path = workbench_preset_path(base_dir);
    let outcome = PRESET_TRANSACTIONS
        .run_remembering(
            &path,
            PresetFlightKey,
            |outcome| matches!(outcome, PresetLoadOutcome::Invalid(_)),
            || async {
            let Some(raw) = read_optional_bytes(&path, "workbench preset").await? else {
                return Ok::<PresetLoadOutcome, ShellError>(PresetLoadOutcome::Missing);
            };
            let entry = match serde_json::from_slice::<WorkbenchPresetEntry>(&raw) {
                Ok(entry) => entry,
                Err(error) => {
                    quarantine_file(&path, QuarantineReason::Corrupt).await?;
                    return Ok(PresetLoadOutcome::Invalid(format!(
                        "Workbench preset is corrupt and was quarantined: {error}"
                    )));
                }
            };
            if entry.schema_version != WORKBENCH_PRESET_SCHEMA_VERSION {
                quarantine_file(
                    &path,
                    QuarantineReason::from_version(&entry.schema_version),
                )
                .await?;
                return Ok(PresetLoadOutcome::Invalid(format!(
                    "Workbench preset schema {} is incompatible with schema {} and was quarantined.",
                    entry.schema_version, WORKBENCH_PRESET_SCHEMA_VERSION
                )));
            }
            Ok(PresetLoadOutcome::Found(Box::new(entry.preset)))
            },
        )
        .await?;
    match outcome {
        PresetLoadOutcome::Missing => Ok(None),
        PresetLoadOutcome::Found(preset) => Ok(Some(*preset)),
        PresetLoadOutcome::Invalid(message) => Err(ShellError::SchemaValidation(message)),
    }
}

pub(crate) async fn save_workbench_preset(
    base_dir: &Path,
    preset: &WorkbenchPreset,
) -> Result<(), ShellError> {
    let entry = serde_json::from_value::<WorkbenchPresetEntry>(json!({
        "schemaVersion": WORKBENCH_PRESET_SCHEMA_VERSION,
        "preset": preset,
    }))
    .map_err(|error| {
        ShellError::SchemaValidation(format!(
            "Unable to construct workbench preset contract: {error}"
        ))
    })?;
    let path = workbench_preset_path(base_dir);
    PRESET_TRANSACTIONS
        .exclusive(&path, || async {
            let result = atomic_write_json(&path, &entry).await;
            if result.is_ok() {
                PRESET_TRANSACTIONS.clear_remembered(&path);
            }
            result
        })
        .await
}

async fn quarantine_file(path: &Path, reason: QuarantineReason) -> Result<(), ShellError> {
    let timestamp = std::time::SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let sequence = QUARANTINE_SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("vp-workbench.json");
    let backup = path.with_file_name(format!(
        "{file_name}.incompatible-{reason}-{timestamp}-{sequence}.bak"
    ));
    match fs::rename(path, &backup).await {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(ShellError::Persistence(format!(
            "Unable to quarantine incompatible persistence file {}: {error}",
            path.display()
        ))),
    }
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
        build_environment_fingerprint, environment_cache_path, load_environment_cache_entry,
        load_workbench_preset, resolve_environment_cache, save_environment_cache_entry,
        save_workbench_preset, workbench_preset_path, QuarantineReason, ENVIRONMENT_TRANSACTIONS,
    };
    use crate::models::config::{
        DecodeConfig, DecodeMode, EncodeConfig, FpsMode, InferenceEngine, InterpolationConfig,
        OutputConfig, PostprocessConfig, PreprocessConfig, ProcessOrder, RateControlConfig,
        SuperResolutionConfig, TensorBackend, WorkbenchPreset, WorkflowConfig,
    };
    use crate::models::EnvironmentCheckResult;
    use crate::runtime::ResolvedRuntimePaths;
    use serde_json::json;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::{env, fs};
    use tokio::sync::Barrier;
    use tokio::time::{sleep, Duration};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    #[tokio::test]
    async fn environment_fingerprint_excludes_output_path_state() {
        // jscpd:ignore-start -- explicit path fixture mirrors env_map coverage.
        let paths = ResolvedRuntimePaths {
            app_data_dir: PathBuf::from("data"),
            backend_dir: PathBuf::from("backend"),
            runtime_root: Some(PathBuf::from("runtime")),
            python_executable: PathBuf::from("python"),
            ffmpeg_path: Some(PathBuf::from("ffmpeg")),
            ffprobe_path: Some(PathBuf::from("ffprobe")),
            model_dir: Some(PathBuf::from("models")),
            rife_model_version: "4.25".to_string(),
            tensorrt_dir: None,
            log_dir: PathBuf::from("logs"),
        };
        // jscpd:ignore-end

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

    // jscpd:ignore-start -- wire-complete preset is declarative test fixture data.
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
                    engine: InferenceEngine::Cuda,
                },
                super_resolution: SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                    onnx_model: None,
                    tensor_backend: TensorBackend::Onnx,
                    engine: InferenceEngine::Cuda,
                    num_frames: 10.try_into().expect("positive frame window"),
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
                rate_control: serde_json::from_value::<RateControlConfig>(json!({
                    "mode": "cq",
                    "value": 23
                }))
                .expect("rate control contract"),
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: Some(
                    "D:/output"
                        .to_string()
                        .try_into()
                        .expect("valid output directory"),
                ),
                open_on_complete: true,
                segment_frames: 1000.try_into().expect("positive segment size"),
            },
        }
    }
    // jscpd:ignore-end

    fn sample_environment_result() -> EnvironmentCheckResult {
        serde_json::from_value(json!({
            "ffmpeg": {
                "available": true,
                "hwaccels": [],
                "encoderProfiles": [],
                "decoderProfiles": []
            },
            "gpu": { "adapters": [] },
            "tensorEngines": { "pytorch": [], "paddle": [], "onnx": [] },
            "interpolationAlgorithms": [],
            "superResolutionAlgorithms": [],
            "runtimeMode": "external"
        }))
        .expect("sample environment result")
    }

    async fn load_cache_entry(
        base_dir: &std::path::Path,
        fingerprint: &str,
        force_refresh: bool,
    ) -> Result<Option<(String, EnvironmentCheckResult)>, crate::error::ShellError> {
        let path = environment_cache_path(base_dir);
        ENVIRONMENT_TRANSACTIONS
            .exclusive(&path, || async {
                load_environment_cache_entry(&path, fingerprint, force_refresh).await
            })
            .await
    }

    async fn save_cache_entry(
        base_dir: &std::path::Path,
        checked_at: &str,
        fingerprint: &str,
        result: &EnvironmentCheckResult,
    ) -> Result<(), crate::error::ShellError> {
        let path = environment_cache_path(base_dir);
        ENVIRONMENT_TRANSACTIONS
            .exclusive(&path, || async {
                save_environment_cache_entry(&path, checked_at, fingerprint, result).await
            })
            .await
    }

    fn has_quarantined_file(dir: &PathBuf, prefix: &str) -> bool {
        fs::read_dir(dir).expect("read test dir").any(|entry| {
            entry
                .ok()
                .and_then(|entry| entry.file_name().into_string().ok())
                .is_some_and(|name| name.starts_with(prefix) && name.ends_with(".bak"))
        })
    }

    fn quarantined_file_count(dir: &PathBuf, prefix: &str) -> usize {
        fs::read_dir(dir)
            .expect("read test dir")
            .filter_map(Result::ok)
            .filter_map(|entry| entry.file_name().into_string().ok())
            .filter(|name| name.starts_with(prefix) && name.ends_with(".bak"))
            .count()
    }

    #[test]
    fn invalid_schema_versions_use_a_path_safe_quarantine_reason() {
        for version in [json!("../escape"), json!({"nested": true}), json!(-1)] {
            assert_eq!(
                QuarantineReason::from_version(&version).to_string(),
                "corrupt-version"
            );
        }
        assert_eq!(
            QuarantineReason::from_version(&json!(12)).to_string(),
            "v12"
        );
    }

    #[tokio::test]
    async fn reuses_valid_environment_cache() {
        let dir = temp_dir("env-hit");
        save_cache_entry(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &sample_environment_result(),
        )
        .await
        .expect("write env cache");

        let (checked_at, result) = load_cache_entry(&dir, "fingerprint-a", false)
            .await
            .expect("read cache")
            .expect("cache hit");
        assert_eq!(checked_at, "2026-04-23T11:00:00Z");
        assert_eq!(
            serde_json::to_value(result).expect("serialize cached result")["runtimeMode"],
            "external"
        );
    }

    #[tokio::test]
    async fn invalidates_environment_cache_when_fingerprint_changes() {
        let dir = temp_dir("env-fingerprint");
        save_cache_entry(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &sample_environment_result(),
        )
        .await
        .expect("write env cache");

        let entry = load_cache_entry(&dir, "fingerprint-b", false)
            .await
            .expect("read cache");
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn invalidates_environment_cache_with_previous_schema_version() {
        let dir = temp_dir("env-schema-v14");
        let payload = serde_json::to_vec_pretty(&json!({
            "schemaVersion": 14,
            "checkedAt": "2026-07-11T12:00:00Z",
            "fingerprint": "fingerprint-a",
            "result": sample_environment_result(),
        }))
        .expect("serialize env cache");
        fs::write(environment_cache_path(&dir), payload).expect("write env cache");

        let entry = load_cache_entry(&dir, "fingerprint-a", false)
            .await
            .expect("read cache");
        assert!(entry.is_none());
        assert!(has_quarantined_file(
            &dir,
            "environment-cache.json.incompatible-v14-"
        ));
    }

    #[tokio::test]
    async fn ignores_damaged_environment_cache() {
        let dir = temp_dir("env-damaged");
        fs::write(environment_cache_path(&dir), "{not-json").expect("write invalid cache");

        let entry = load_cache_entry(&dir, "fingerprint-a", false)
            .await
            .expect("read cache");
        assert!(entry.is_none());
        assert!(has_quarantined_file(
            &dir,
            "environment-cache.json.incompatible-corrupt-"
        ));
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_corrupt_cache_reads_quarantine_once_and_rebuild_consistently() {
        let dir = temp_dir("env-concurrent-damaged");
        fs::write(environment_cache_path(&dir), "{not-json").expect("write invalid cache");

        let readers = (0..16)
            .map(|_| {
                let dir = dir.clone();
                tokio::spawn(async move { load_cache_entry(&dir, "fingerprint-a", false).await })
            })
            .collect::<Vec<_>>();

        for reader in readers {
            let entry = reader
                .await
                .expect("cache reader task")
                .expect("corrupt cache is treated as a miss");
            assert!(entry.is_none());
        }
        assert_eq!(
            quarantined_file_count(&dir, "environment-cache.json.incompatible-corrupt-"),
            1
        );
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_environment_transactions_probe_once_and_return_one_payload() {
        for iteration in 0..100 {
            let dir = temp_dir(&format!("env-concurrent-transaction-{iteration}"));
            fs::write(environment_cache_path(&dir), "{not-json").expect("write invalid cache");
            let probe_count = Arc::new(AtomicUsize::new(0));
            let start = Arc::new(Barrier::new(16));

            let callers = (0..16)
                .map(|index| {
                    let dir = if index % 2 == 0 {
                        dir.clone()
                    } else {
                        dir.join(".")
                    };
                    let probe_count = Arc::clone(&probe_count);
                    let start = Arc::clone(&start);
                    tokio::spawn(async move {
                        start.wait().await;
                        resolve_environment_cache(&dir, "fingerprint-a", false, || async move {
                            probe_count.fetch_add(1, Ordering::SeqCst);
                            sleep(Duration::from_millis(25)).await;
                            Ok(sample_environment_result())
                        })
                        .await
                    })
                })
                .collect::<Vec<_>>();

            let mut payloads = Vec::new();
            for caller in callers {
                payloads.push(
                    caller
                        .await
                        .expect("environment caller task")
                        .expect("environment transaction"),
                );
            }
            assert_eq!(probe_count.load(Ordering::SeqCst), 1);
            let expected = serde_json::to_value(&payloads[0]).expect("serialize first payload");
            assert!(payloads.iter().all(|payload| {
                serde_json::to_value(payload).expect("serialize payload") == expected
            }));
            fs::remove_dir_all(&dir).expect("remove concurrent transaction fixture");
        }
    }

    #[tokio::test]
    async fn completed_environment_flight_reloads_the_persisted_cache() {
        let dir = temp_dir("env-flight-complete");
        let probe_count = Arc::new(AtomicUsize::new(0));
        let first_probe_count = Arc::clone(&probe_count);
        let first = resolve_environment_cache(&dir, "fingerprint-a", false, || async move {
            first_probe_count.fetch_add(1, Ordering::SeqCst);
            Ok(sample_environment_result())
        })
        .await
        .expect("initial probe");
        let second_probe_count = Arc::clone(&probe_count);
        let second = resolve_environment_cache(&dir, "fingerprint-a", false, || async move {
            second_probe_count.fetch_add(1, Ordering::SeqCst);
            Ok(sample_environment_result())
        })
        .await
        .expect("cached environment");

        assert_eq!(probe_count.load(Ordering::SeqCst), 1);
        assert_eq!(
            serde_json::to_value(first.source).expect("serialize source"),
            json!("probe")
        );
        assert_eq!(
            serde_json::to_value(second.source).expect("serialize source"),
            json!("cache")
        );
        assert_eq!(first.checked_at, second.checked_at);
    }

    #[tokio::test]
    async fn quarantines_non_utf8_environment_cache() {
        let dir = temp_dir("env-non-utf8");
        fs::write(environment_cache_path(&dir), [0xff, 0xfe]).expect("write invalid cache");

        let entry = load_cache_entry(&dir, "fingerprint-a", false)
            .await
            .expect("read cache");

        assert!(entry.is_none());
        assert!(has_quarantined_file(
            &dir,
            "environment-cache.json.incompatible-corrupt-"
        ));
    }

    #[tokio::test]
    async fn bypasses_environment_cache_when_force_refresh_is_enabled() {
        let dir = temp_dir("env-force-refresh");
        save_cache_entry(
            &dir,
            "2026-04-23T11:00:00Z",
            "fingerprint-a",
            &sample_environment_result(),
        )
        .await
        .expect("write env cache");

        let entry = load_cache_entry(&dir, "fingerprint-a", true)
            .await
            .expect("read cache");
        assert!(entry.is_none());
    }

    #[tokio::test]
    async fn loads_saved_workbench_preset() {
        let dir = temp_dir("preset");
        let preset = sample_preset();

        save_workbench_preset(&dir, &preset)
            .await
            .expect("save preset");

        let loaded = load_workbench_preset(&dir)
            .await
            .expect("read preset")
            .expect("load preset");
        assert_eq!(loaded.decode_config.decoder.as_deref(), Some("hevc_cuvid"));
        assert_eq!(loaded.encode_config.codec, "hevc_nvenc");
    }

    #[tokio::test]
    async fn quarantines_workbench_preset_with_unknown_schema_version() {
        let dir = temp_dir("preset-schema");
        let payload = serde_json::to_vec_pretty(&json!({
            "schemaVersion": 999,
            "preset": sample_preset(),
        }))
        .expect("serialize preset");
        fs::write(workbench_preset_path(&dir), payload).expect("write preset");

        let loaded = load_workbench_preset(&dir).await;
        assert!(matches!(
            loaded,
            Err(crate::error::ShellError::SchemaValidation(_))
        ));
        assert!(has_quarantined_file(
            &dir,
            "workbench-preset.json.incompatible-v999-"
        ));
    }

    #[tokio::test]
    async fn quarantines_non_utf8_workbench_preset_as_a_schema_error() {
        let dir = temp_dir("preset-non-utf8");
        fs::write(workbench_preset_path(&dir), [0xff, 0xfe]).expect("write invalid preset");

        let loaded = load_workbench_preset(&dir).await;

        assert!(matches!(
            loaded,
            Err(crate::error::ShellError::SchemaValidation(_))
        ));
        assert!(has_quarantined_file(
            &dir,
            "workbench-preset.json.incompatible-corrupt-"
        ));
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_corrupt_preset_reads_return_the_same_schema_error() {
        let dir = temp_dir("preset-concurrent-corrupt");
        fs::write(workbench_preset_path(&dir), "{not-json").expect("write invalid preset");
        let start = Arc::new(Barrier::new(16));
        let readers = (0..16)
            .map(|index| {
                let dir = if index % 2 == 0 {
                    dir.clone()
                } else {
                    dir.join(".")
                };
                let start = Arc::clone(&start);
                tokio::spawn(async move {
                    start.wait().await;
                    load_workbench_preset(&dir).await
                })
            })
            .collect::<Vec<_>>();

        let mut messages = Vec::new();
        for reader in readers {
            match reader.await.expect("preset reader task") {
                Err(crate::error::ShellError::SchemaValidation(message)) => {
                    messages.push(message);
                }
                other => panic!("all concurrent readers must observe the schema error: {other:?}"),
            }
        }
        assert_eq!(messages.len(), 16);
        assert!(messages.iter().all(|message| message == &messages[0]));
        assert_eq!(
            quarantined_file_count(&dir, "workbench-preset.json.incompatible-corrupt-"),
            1
        );
    }

    #[tokio::test]
    async fn saving_a_rebuilt_preset_clears_the_remembered_schema_error() {
        let dir = temp_dir("preset-rebuild");
        fs::write(workbench_preset_path(&dir), "{not-json").expect("write invalid preset");
        assert!(matches!(
            load_workbench_preset(&dir).await,
            Err(crate::error::ShellError::SchemaValidation(_))
        ));
        assert!(matches!(
            load_workbench_preset(&dir).await,
            Err(crate::error::ShellError::SchemaValidation(_))
        ));

        let preset = sample_preset();
        save_workbench_preset(&dir, &preset)
            .await
            .expect("save rebuilt preset");
        let loaded = load_workbench_preset(&dir)
            .await
            .expect("load rebuilt preset")
            .expect("rebuilt preset exists");
        assert_eq!(loaded.encode_config.codec, preset.encode_config.codec);
    }
}
