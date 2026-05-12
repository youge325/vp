//! RIFE 模型目录 / TensorRT 目录 解析,以及默认权重文件名常量。

use std::path::PathBuf;

use super::helpers::{env_path, first_existing_dir};

/// Release 构建强制要求 ``$MODEL_DIR/<DEFAULT_RIFE_MODEL_FILENAME>`` 存在。
///
/// 文件名硬编码在原 ``runtime.rs::default_rife_model_file()`` 里,Phase C.2.1
/// 把它提到常量以消除魔法字符串。需要切换版本时改这一处即可。
pub(super) const DEFAULT_RIFE_MODEL_FILENAME: &str = "flownet_v4.25.pkl";

pub(super) fn resolve_model_dir(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
    workspace_root: &PathBuf,
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

pub(super) fn resolve_tensorrt_dir(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
) -> Option<PathBuf> {
    first_existing_dir([
        env_path("VP_TENSORRT_DIR"),
        runtime_root.map(|path| path.join("tensorrt")),
        resource_dir.map(|path| path.join("tensorrt")),
    ])
}

/// 检查 ``$MODEL_DIR/<DEFAULT_RIFE_MODEL_FILENAME>`` 是否真实存在。
pub(super) fn has_default_rife_model(model_dir: Option<&PathBuf>) -> bool {
    model_dir
        .map(|path| path.join(DEFAULT_RIFE_MODEL_FILENAME).is_file())
        .unwrap_or(false)
}
