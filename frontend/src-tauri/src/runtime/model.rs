//! RIFE 模型目录 / TensorRT 目录 解析,以及默认权重文件名常量。

use std::path::{Path, PathBuf};

use super::helpers::{env_path, first_existing_dir};

/// Release 构建强制要求 ``$MODEL_DIR/<DEFAULT_RIFE_MODEL_FILENAME>`` 存在。
///
/// 文件名硬编码在原 ``runtime.rs::default_rife_model_file()`` 里,Phase C.2.1
/// 把它提到常量以消除魔法字符串。需要切换版本时改这一处即可。
pub(super) const DEFAULT_RIFE_MODEL_FILENAME: &str = "flownet_v4.25.pkl";

pub(super) fn resolve_model_dir(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
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
        resource_dir.map(|path| path.join("models")),
        resource_dir.map(|path| path.join("backend").join("models")),
        dev_model_dir,
    ])
}

/// Resolve the TensorRT install directory used by the Python backend.
///
/// Search order:
/// 1. ``VP_TENSORRT_DIR`` env variable, **if it points to an existing
///    directory** (handled by [`first_existing_dir`]).
/// 2. ``$RUNTIME_ROOT/tensorrt`` (bundled location, if present).
/// 3. ``$RESOURCE/tensorrt`` (alternate bundle layout).
/// 4. **Phase 12 fallback** — if none of the above resolves to an
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
pub(super) fn resolve_tensorrt_dir(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
) -> Option<PathBuf> {
    if let Some(existing) = first_existing_dir([
        env_path("VP_TENSORRT_DIR"),
        runtime_root.map(|path| path.join("tensorrt")),
        resource_dir.map(|path| path.join("tensorrt")),
    ]) {
        return Some(existing);
    }

    // Phase 12 — env-only fallback. ``env_path`` already filters empty
    // values via ``env::var_os``, but we double-check here because the
    // backend treats an empty ``VP_TENSORRT_DIR`` the same as unset and
    // we don't want to spam it with a useless variable.
    env_path("VP_TENSORRT_DIR").filter(|path| !path.as_os_str().is_empty())
}

/// 检查 ``$MODEL_DIR/<DEFAULT_RIFE_MODEL_FILENAME>`` 是否真实存在。
pub(super) fn has_default_rife_model(model_dir: Option<&PathBuf>) -> bool {
    model_dir
        .map(|path| path.join(DEFAULT_RIFE_MODEL_FILENAME).is_file())
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime::test_support::VP_TENSORRT_DIR_LOCK;
    use std::env;

    const TENSORRT_ENV_KEY: &str = "VP_TENSORRT_DIR";

    /// RAII guard that restores ``VP_TENSORRT_DIR`` to whatever the process
    /// had before the test ran, so test ordering / parallel runs don't leak
    /// state into each other.
    ///
    /// Phase 13.2 CI hotfix — additionally holds
    /// [`VP_TENSORRT_DIR_LOCK`] for the duration of the test. Without it,
    /// ``cargo test`` running these cases in parallel on multi-core CI
    /// could read another test's ``set_var`` value before that test's
    /// guard dropped (observed in GitHub Actions Phase 13.1 build), with
    /// the env-only fallback never getting a chance to fire.
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
        assert_eq!(resolve_tensorrt_dir(None, None), None);
    }

    #[test]
    fn resolve_tensorrt_dir_passes_env_through_even_when_path_missing() {
        // Phase 12 — the runtime/model layer is the single owner of the
        // "trust the user's env var even if the directory doesn't exist
        // yet" semantics. Previously this fallback lived in env_map.rs,
        // which silently disagreed with the paths layer about whether
        // the variable was honoured.
        let guard = EnvGuard::capture();
        let missing = std::env::current_dir()
            .unwrap()
            .join("__phase12_nonexistent_tensorrt__");
        guard.set(missing.to_string_lossy().as_ref());
        let resolved = resolve_tensorrt_dir(None, None);
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
        let resolved = resolve_tensorrt_dir(None, None);
        assert_eq!(resolved.as_deref(), Some(real.as_path()));
    }

    #[test]
    fn resolve_tensorrt_dir_ignores_empty_env() {
        // Empty value mustn't leak through as ``Some("")`` — the backend
        // treats an empty ``VP_TENSORRT_DIR`` the same as unset and we
        // don't want a confusing env entry.
        let guard = EnvGuard::capture();
        guard.set("");
        assert_eq!(resolve_tensorrt_dir(None, None), None);
    }
}
