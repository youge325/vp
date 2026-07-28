//! Python 可执行文件路径解析。
//!
//! 解析顺序:
//!   1. ``VP_PYTHON_EXECUTABLE`` 环境变量(绝对路径,适合 CI / 多 venv 切换)
//!   2. ``$RUNTIME_ROOT/python/python.exe`` 等打包位置
//!   3. 系统 ``PATH``(开发环境 / 用户已装 Python 3.12+)
//!
//! Release 构建不再打包 Python 运行时(README 已说明),所以 fallback 到
//! 系统 PATH 是合法路径,而不是 error。

use std::path::PathBuf;

use crate::error::ShellError;

use super::helpers::{env_path, find_in_system_path, first_existing_file, platform_python_binary};

const MISSING_PYTHON_MESSAGE: &str =
    "Python executable not found. Set VP_PYTHON_EXECUTABLE, install Python in your system PATH, or bundle resources/runtime/python/.";

pub(super) fn resolve_python_executable(
    runtime_root: Option<&PathBuf>,
) -> Result<PathBuf, ShellError> {
    let bin = platform_python_binary();
    let candidates = [
        env_path("VP_PYTHON_EXECUTABLE"),
        bundled_python_path(runtime_root, bin),
    ];

    if let Some(path) = first_existing_file(candidates) {
        return Ok(path);
    }

    find_in_system_path(bin)
        .ok_or_else(|| ShellError::RuntimeResolution(MISSING_PYTHON_MESSAGE.to_string()))
}

fn bundled_python_path(runtime_root: Option<&PathBuf>, binary: &str) -> Option<PathBuf> {
    first_existing_file([runtime_root.map(|path| path.join("python").join(binary))])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_python_resolves_the_canonical_runtime_layout() {
        let temp = tempfile::tempdir().expect("temp dir");
        let runtime = temp.path().join("runtime");
        let binary = platform_python_binary();
        let canonical = runtime.join("python").join(binary);
        std::fs::create_dir_all(canonical.parent().expect("python parent"))
            .expect("create python parent");
        std::fs::write(&canonical, b"python").expect("write python");

        assert_eq!(
            bundled_python_path(Some(&runtime), binary),
            Some(canonical.clone())
        );
        std::fs::remove_file(canonical).expect("remove canonical python");
        assert_eq!(bundled_python_path(Some(&runtime), binary), None);
    }
}
