//! 运行时路径解析编排层。
//!
//! 入口:[`resolve_runtime_paths`] 把所有候选位置串起来,返回
//! [`ResolvedRuntimePaths`] 给 Tauri 命令使用。子模块各自只回答一个问题
//! (python / ffmpeg / model / env_map),本文件只做装配 + dev/release
//! 必需性检查 + app_data 目录创建。
//!
//! 历史:在 Phase C.2.1 之前是一个 387 行的 ``runtime.rs``;拆分后单文件最长
//! ``mod.rs`` ~150 行,职责一目了然。

mod env_map;
mod ffmpeg;
mod helpers;
mod model;
mod python;

use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager, Runtime};

use crate::error::ShellError;

// 对外只导出 3 个 API,与 Phase C.2.1 之前完全兼容(builder/runner/lib/
// persistence/services/environment_service 仍可直接 ``use crate::runtime::*``)。
pub use env_map::build_env_map;
use helpers::{directory_if_contains, first_existing_dir};
use model::{has_default_rife_model, DEFAULT_RIFE_MODEL_FILENAME};

#[derive(Debug, Clone)]
pub struct ResolvedRuntimePaths {
    pub backend_dir: PathBuf,
    pub runtime_root: Option<PathBuf>,
    pub python_executable: PathBuf,
    pub ffmpeg_path: Option<PathBuf>,
    pub ffprobe_path: Option<PathBuf>,
    pub model_dir: Option<PathBuf>,
    pub tensorrt_dir: Option<PathBuf>,
    pub log_dir: PathBuf,
}

pub fn resolve_runtime_paths<R: Runtime>(
    app: &AppHandle<R>,
) -> Result<ResolvedRuntimePaths, ShellError> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let frontend_dir = manifest_dir
        .parent()
        .ok_or_else(|| {
            ShellError::RuntimeResolution("Unable to resolve frontend directory.".to_string())
        })?
        .to_path_buf();
    let workspace_root = frontend_dir
        .parent()
        .ok_or_else(|| {
            ShellError::RuntimeResolution("Unable to resolve workspace root.".to_string())
        })?
        .to_path_buf();
    let resource_dir = app.path().resource_dir().ok();

    let backend_dir = resolve_backend_dir(&workspace_root, resource_dir.as_ref())?;
    let runtime_root = resolve_runtime_root(&frontend_dir, resource_dir.as_ref());

    let python_executable = python::resolve_python_executable(runtime_root.as_ref())?;

    let ffmpeg_path = ffmpeg::resolve_ffmpeg_path(runtime_root.as_ref(), resource_dir.as_ref());
    let ffprobe_path = ffmpeg::resolve_ffprobe_path(runtime_root.as_ref(), resource_dir.as_ref());
    let model_dir = model::resolve_model_dir(
        runtime_root.as_ref(),
        resource_dir.as_ref(),
        &workspace_root,
    );
    let tensorrt_dir = model::resolve_tensorrt_dir(runtime_root.as_ref(), resource_dir.as_ref());

    require_release_bundle_artifacts(&ffmpeg_path, &ffprobe_path, &model_dir)?;

    // Phase 16 — ``app_local_data_dir()`` 失败的兜底按 build 模式分流:
    // - debug:走 ``<workspace>/.tmp/app-data``,保持开发便利(本地测试
    //   时 Tauri 还没注入 app_local_data_dir 也能跑)。
    // - release:直接报 ``RuntimeResolution`` 拒绝启动。release 跑在
    //   ``Program Files`` 或安装目录,``workspace_root = CARGO_MANIFEST_DIR/..``
    //   可能不存在或不可写,默默落到那里再 ``create_dir_all`` 出错的话,
    //   错误链路里看不到"为什么是这个路径",诊断成本高。release 下
    //   ``app_local_data_dir`` 本就稳定指向 ``%LOCALAPPDATA%\<bundle-id>``,
    //   失败大概率是 Tauri 初始化破损,fail-loudly 反而干净。
    let app_data_dir = if let Some(path) = helpers::env_path("VP_APP_DATA_DIR") {
        path
    } else {
        match app.path().app_local_data_dir() {
            Ok(path) => path,
            Err(error) => {
                if cfg!(debug_assertions) {
                    workspace_root.join(".tmp").join("app-data")
                } else {
                    return Err(ShellError::RuntimeResolution(format!(
                        "Unable to resolve app local data dir: {error}",
                    )));
                }
            }
        }
    };

    // E2E 测试中多个实例快速串行启动，共享同一个日志文件会导致
    // WinError 32（文件被占用）。允许通过 VP_LOG_DIR 环境变量为每个
    //实例指定独立的日志目录。
    let log_dir = helpers::env_path("VP_LOG_DIR").unwrap_or_else(|| app_data_dir.join("logs"));

    std::fs::create_dir_all(&log_dir)?;

    Ok(ResolvedRuntimePaths {
        backend_dir,
        runtime_root,
        python_executable,
        ffmpeg_path,
        ffprobe_path,
        model_dir,
        tensorrt_dir,
        log_dir,
    })
}

fn resolve_backend_dir(
    workspace_root: &Path,
    resource_dir: Option<&PathBuf>,
) -> Result<PathBuf, ShellError> {
    let resource_backend = resource_dir.and_then(|path| {
        directory_if_contains(path, "app")
            .or_else(|| Some(path.join("backend")).filter(|p| p.is_dir()))
    });

    let dev_backend_dir = if cfg!(debug_assertions) {
        Some(workspace_root.join("backend"))
    } else {
        None
    };

    first_existing_dir([
        helpers::env_path("VP_BACKEND_DIR"),
        resource_backend,
        dev_backend_dir,
    ])
    .ok_or_else(|| ShellError::RuntimeResolution("Unable to locate backend directory.".to_string()))
}

fn resolve_runtime_root(frontend_dir: &Path, resource_dir: Option<&PathBuf>) -> Option<PathBuf> {
    let dev_runtime_root = if cfg!(debug_assertions) {
        Some(
            frontend_dir
                .join("src-tauri")
                .join("resources")
                .join("runtime"),
        )
    } else {
        None
    };
    first_existing_dir([
        helpers::env_path("VP_RUNTIME_ROOT"),
        resource_dir.map(|path| path.join("resources").join("runtime")),
        resource_dir.map(|path| path.join("runtime")),
        dev_runtime_root,
    ])
}

/// Release 构建必须打包 FFmpeg / FFprobe / 默认 RIFE 模型,否则拒绝启动。
///
/// Dev 构建允许缺失,后端 ``app.utils.ffmpeg.FFmpegWrapper`` 会用 ``shutil.which``
/// 兜底。
fn require_release_bundle_artifacts(
    ffmpeg_path: &Option<PathBuf>,
    ffprobe_path: &Option<PathBuf>,
    model_dir: &Option<PathBuf>,
) -> Result<(), ShellError> {
    if cfg!(debug_assertions) {
        return Ok(());
    }
    if ffmpeg_path.is_none() {
        return Err(ShellError::RuntimeResolution(
            "Bundled FFmpeg is missing. Set VP_FFMPEG_PATH or include resources/runtime/ffmpeg/bin/ffmpeg.exe."
                .to_string(),
        ));
    }
    if ffprobe_path.is_none() {
        return Err(ShellError::RuntimeResolution(
            "Bundled FFprobe is missing. Set VP_FFPROBE_PATH or include resources/runtime/ffmpeg/bin/ffprobe.exe."
                .to_string(),
        ));
    }
    if !has_default_rife_model(model_dir.as_ref()) {
        return Err(ShellError::RuntimeResolution(format!(
            "Bundled RIFE model is missing. Set VP_RIFE_MODEL_DIR or include resources/runtime/models/{DEFAULT_RIFE_MODEL_FILENAME}.",
        )));
    }
    Ok(())
}

// Phase 13.2 hotfix — Phase 12A 在 ``runtime/model.rs`` 与
// ``runtime/env_map.rs`` 各加了改写 ``VP_TENSORRT_DIR`` 的测试,但没共享
// 互斥锁。``cargo test`` 在多核 CI(GitHub Actions Windows runner)上把
// 这些测试并行调度时,后台的 ``*_prefers_existing_dir_over_env_fallback``
// 把变量设成 cwd 后还没 RAII restore,前台的
// ``*_passes_env_through_even_when_path_missing`` 已经读 env_path 进入
// first_existing_dir 命中 cwd,fallback 路径压根没机会跑。本地单线程
// cargo test 串行不触发,但 CI 上 100% 复现。
//
// 把 ``VP_TENSORRT_DIR`` 的 set/restore 串行化到这把锁后,所有 5 个
// 改 env 的测试(4 个 model + 1 个 env_map)就互不干扰了。pub(crate)
// 范围确保 lib 外不可见;静态 const-fn ``Mutex::new(())`` 不依赖任何
// init order。
#[cfg(test)]
pub(crate) mod test_support {
    use std::sync::Mutex;
    pub static VP_TENSORRT_DIR_LOCK: Mutex<()> = Mutex::new(());
}
