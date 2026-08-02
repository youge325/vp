//! RIFE 模型目录 / TensorRT 目录 解析,以及默认权重文件名常量。

use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use super::helpers::{env_path, first_existing_dir};
use crate::generated::{
    ModelAssetVariant, REAL_RAWVSR_BASICVSR_LICENSE_PATH, REAL_RAWVSR_BASICVSR_NOTICE_PATH,
    REAL_RAWVSR_BASICVSR_VARIANTS,
};

pub(super) fn rife_model_filename(version: &str) -> String {
    format!("flownet_v{version}.pkl")
}

pub(super) fn resolve_model_dir(
    runtime_root: Option<&PathBuf>,
    workspace_root: &Path,
) -> Option<PathBuf> {
    let dev_model_dir = if cfg!(debug_assertions) {
        Some(workspace_root.join("backend").join("models"))
    } else {
        None
    };
    first_existing_dir([
        env_path("VP_RIFE_MODEL_DIR"),
        runtime_root.map(|path| path.join("models")),
        dev_model_dir,
    ])
}

/// Resolve the TensorRT install directory used by the Python backend.
///
/// Search order:
/// 1. ``VP_TENSORRT_DIR`` env variable, **if it points to an existing
///    directory** (handled by [`first_existing_dir`]).
/// 2. ``$RUNTIME_ROOT/tensorrt`` (bundled location, if present).
/// 3. If neither of the above resolves to an
///    existing directory but ``VP_TENSORRT_DIR`` is set in the
///    environment with a non-empty value, we pass it through verbatim
///    **even if the directory does not currently exist**. Users may
///    intentionally point this at a path they have not yet extracted
///    (e.g. "TensorRT-10.x will live here once I download it"), and
///    the backend's own DLL probe handles the "directory missing" case
///    with a clearer error than refusing to set the variable would.
///
/// This collapses what used to be a split between paths-layer
/// resolution and ``env_map`` fallback into a single decision point.
/// ``env_map`` now just forwards ``paths.tensorrt_dir`` to the backend
/// when it is set, no second peek at ``std::env::var`` required.
pub(super) fn resolve_tensorrt_dir(runtime_root: Option<&PathBuf>) -> Option<PathBuf> {
    if let Some(existing) = first_existing_dir([
        env_path("VP_TENSORRT_DIR"),
        runtime_root.map(|path| path.join("tensorrt")),
    ]) {
        return Some(existing);
    }

    // Environment-only fallback. `env_path` is the single empty-value filter.
    env_path("VP_TENSORRT_DIR")
}

/// 检查 ``$MODEL_DIR/<DEFAULT_RIFE_MODEL_FILENAME>`` 是否真实存在。
pub(super) fn has_rife_model(model_dir: Option<&PathBuf>, version: &str) -> bool {
    model_dir
        .map(|path| path.join(rife_model_filename(version)))
        .and_then(|path| path.metadata().ok())
        .map(|metadata| metadata.is_file() && metadata.len() > 0)
        .unwrap_or(false)
}

pub(super) fn validate_real_rawvsr_bundle(
    model_dir: Option<&PathBuf>,
    license_root: &Path,
) -> Result<(), String> {
    let model_dir = model_dir.ok_or_else(|| "Bundled model directory is missing.".to_string())?;
    for relative_path in [
        REAL_RAWVSR_BASICVSR_LICENSE_PATH,
        REAL_RAWVSR_BASICVSR_NOTICE_PATH,
    ] {
        let path = license_root.join(relative_path);
        let metadata = path.metadata().map_err(|error| {
            format!(
                "Required Real-RawVSR license file is missing ({}): {error}",
                path.display()
            )
        })?;
        if !metadata.is_file() || metadata.len() == 0 {
            return Err(format!(
                "Required Real-RawVSR license file is empty or invalid: {}",
                path.display()
            ));
        }
    }
    for variant in REAL_RAWVSR_BASICVSR_VARIANTS {
        validate_model_asset(model_dir, variant)?;
    }
    Ok(())
}

fn validate_model_asset(model_dir: &Path, variant: &ModelAssetVariant) -> Result<(), String> {
    let relative_path = Path::new(variant.relative_path)
        .strip_prefix("models")
        .map_err(|_| {
            format!(
                "Model asset path is not rooted under models/: {}",
                variant.relative_path
            )
        })?;
    let path = model_dir.join(relative_path);
    let metadata = path.metadata().map_err(|error| {
        format!(
            "Real-RawVSR BasicVSR x{} model is missing ({}): {error}",
            variant.scale_factor,
            path.display()
        )
    })?;
    if !metadata.is_file() || metadata.len() != variant.inference_bytes {
        return Err(format!(
            "Real-RawVSR BasicVSR x{} model size mismatch: expected {}, got {} ({}).",
            variant.scale_factor,
            variant.inference_bytes,
            metadata.len(),
            path.display()
        ));
    }
    let mut file = File::open(&path).map_err(|error| {
        format!(
            "Unable to read Real-RawVSR model {}: {error}",
            path.display()
        )
    })?;
    let actual = sha256_reader(&mut file).map_err(|error| {
        format!(
            "Unable to hash Real-RawVSR model {}: {error}",
            path.display()
        )
    })?;
    if actual != variant.inference_sha256 {
        return Err(format!(
            "Real-RawVSR BasicVSR x{} model SHA-256 mismatch: expected {}, got {} ({}).",
            variant.scale_factor,
            variant.inference_sha256,
            actual,
            path.display()
        ));
    }
    Ok(())
}

fn sha256_reader(reader: &mut impl Read) -> std::io::Result<String> {
    let mut digest = Sha256::new();
    // Release startup performs this work on the OS main thread, whose stack
    // can be smaller than Rust's test-thread stack. Keep the I/O buffer on the
    // heap so validating bundled models cannot overflow that thread.
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::generated::DEFAULT_RIFE_MODEL_VERSION;
    use crate::runtime::test_support::VP_TENSORRT_DIR_LOCK;
    use std::env;

    const TENSORRT_ENV_KEY: &str = "VP_TENSORRT_DIR";

    /// RAII guard that restores ``VP_TENSORRT_DIR`` to whatever the process
    /// had before the test ran, so test ordering / parallel runs don't leak
    /// state into each other.
    ///
    /// Holds [`VP_TENSORRT_DIR_LOCK`] so parallel tests cannot observe
    /// each other's temporary process-environment values.
    struct EnvGuard {
        original: Option<std::ffi::OsString>,
        _lock: std::sync::MutexGuard<'static, ()>,
    }

    impl EnvGuard {
        fn capture() -> Self {
            // ``unwrap_or_else(into_inner)`` — if a previous test panicked
            // mid-mutation the lock is poisoned, but the data it guards
            // is just a unit ``()`` so we can safely keep going.
            let lock = VP_TENSORRT_DIR_LOCK
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            Self {
                original: env::var_os(TENSORRT_ENV_KEY),
                _lock: lock,
            }
        }

        fn set(&self, value: &str) {
            env::set_var(TENSORRT_ENV_KEY, value);
        }

        fn unset(&self) {
            env::remove_var(TENSORRT_ENV_KEY);
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            match self.original.take() {
                Some(value) => env::set_var(TENSORRT_ENV_KEY, value),
                None => env::remove_var(TENSORRT_ENV_KEY),
            }
        }
    }

    #[test]
    fn resolve_tensorrt_dir_returns_none_when_unset_and_no_bundle() {
        let guard = EnvGuard::capture();
        guard.unset();
        assert_eq!(resolve_tensorrt_dir(None), None);
    }

    #[test]
    fn resolve_tensorrt_dir_passes_env_through_even_when_path_missing() {
        // The runtime/model layer is the single owner of the "trust the
        // user's env var even if the directory doesn't exist yet" semantics.
        let guard = EnvGuard::capture();
        let missing = std::env::current_dir()
            .unwrap()
            .join("__vp_nonexistent_tensorrt__");
        guard.set(missing.to_string_lossy().as_ref());
        let resolved = resolve_tensorrt_dir(None);
        assert_eq!(resolved.as_deref(), Some(missing.as_path()));
    }

    #[test]
    fn resolve_tensorrt_dir_prefers_existing_dir_over_env_fallback() {
        // If the env var IS a real directory it must come out of the
        // first-existing-dir path (no fallback needed), and if it isn't
        // we fall through. Verified here by pointing the env var at the
        // current working directory, which always exists.
        let guard = EnvGuard::capture();
        let real = std::env::current_dir().unwrap();
        guard.set(real.to_string_lossy().as_ref());
        let resolved = resolve_tensorrt_dir(None);
        assert_eq!(resolved.as_deref(), Some(real.as_path()));
    }

    #[test]
    fn resolve_tensorrt_dir_ignores_empty_env() {
        // Empty value mustn't leak through as ``Some("")`` — the backend
        // treats an empty ``VP_TENSORRT_DIR`` the same as unset and we
        // don't want a confusing env entry.
        let guard = EnvGuard::capture();
        guard.set("");
        assert_eq!(resolve_tensorrt_dir(None), None);
    }

    #[test]
    fn has_default_rife_model_returns_false_when_file_is_missing() {
        let temp = tempfile::tempdir().unwrap();
        let model_dir = temp.path().to_path_buf();

        assert!(!has_rife_model(
            Some(&model_dir),
            DEFAULT_RIFE_MODEL_VERSION
        ));
    }

    #[test]
    fn model_hashing_uses_bounded_stack_space() {
        let digest = std::thread::Builder::new()
            .stack_size(128 * 1024)
            .spawn(|| {
                let mut payload = std::io::Cursor::new(vec![7_u8; 2 * 1024 * 1024]);
                sha256_reader(&mut payload).unwrap()
            })
            .unwrap()
            .join()
            .unwrap();

        assert_eq!(
            digest,
            "c406296b30d433e27c08e2989ad557c7e9ae7825d1bea14c42aa4ef53c9e8a9d"
        );
    }

    #[test]
    fn has_default_rife_model_returns_false_for_empty_file() {
        let temp = tempfile::tempdir().unwrap();
        let model_dir = temp.path().to_path_buf();
        std::fs::File::create(model_dir.join(rife_model_filename(DEFAULT_RIFE_MODEL_VERSION)))
            .unwrap();

        assert!(!has_rife_model(
            Some(&model_dir),
            DEFAULT_RIFE_MODEL_VERSION
        ));
    }

    #[test]
    fn has_default_rife_model_returns_true_for_non_empty_file() {
        let temp = tempfile::tempdir().unwrap();
        let model_dir = temp.path().to_path_buf();
        std::fs::write(
            model_dir.join(rife_model_filename(DEFAULT_RIFE_MODEL_VERSION)),
            b"weights",
        )
        .unwrap();

        assert!(has_rife_model(Some(&model_dir), DEFAULT_RIFE_MODEL_VERSION));
    }

    #[test]
    fn model_asset_validation_rejects_hash_drift() {
        let temp = tempfile::tempdir().unwrap();
        let relative_path = "models/test/model.safetensors";
        let path = temp.path().join(relative_path);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, b"safe").unwrap();
        let valid = ModelAssetVariant {
            scale_factor: 2,
            inference_bytes: 4,
            inference_sha256: "8b3369944dd2a3fab39e32d1aeb1f763946a458ae3e6368a46432adc8f3a0860",
            relative_path,
        };
        let model_dir = temp.path().join("models");
        assert!(validate_model_asset(&model_dir, &valid).is_ok());

        let drifted = ModelAssetVariant {
            inference_sha256: "0000000000000000000000000000000000000000000000000000000000000000",
            ..valid
        };
        assert!(validate_model_asset(&model_dir, &drifted)
            .unwrap_err()
            .contains("SHA-256 mismatch"));
    }

    #[test]
    fn release_bundle_validation_rejects_an_omitted_basicvsr_model() {
        let temp = tempfile::tempdir().unwrap();
        let models = temp.path().join("models");
        std::fs::create_dir_all(&models).unwrap();
        for relative_path in [
            REAL_RAWVSR_BASICVSR_LICENSE_PATH,
            REAL_RAWVSR_BASICVSR_NOTICE_PATH,
        ] {
            let path = temp.path().join(relative_path);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, b"license").unwrap();
        }

        let error = validate_real_rawvsr_bundle(Some(&models), temp.path()).unwrap_err();
        assert!(error.contains("BasicVSR x2 model is missing"));
    }
}
