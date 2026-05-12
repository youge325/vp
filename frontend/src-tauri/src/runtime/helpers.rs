//! 跨子模块工具函数 — 路径探测、env 读取、平台二进制名解析。
//!
//! 这些函数与"探测什么资源"无关,只回答"给我一个候选列表,我选第一个存在的"
//! 这类基础问题。所有探测策略(python / ffmpeg / model)再叠加在它们之上。

use std::env;
use std::path::{Path, PathBuf};

/// 从环境变量读路径(空值视为未设)。
pub(super) fn env_path(key: &str) -> Option<PathBuf> {
    env::var_os(key).map(PathBuf::from)
}

/// 如果 ``path`` 包含子目录 ``child``,返回 ``path`` 本身。
///
/// 用于 ``backend`` 目录探测:resource_dir 可能是 ``$RESOURCE/`` 也可能是
/// ``$RESOURCE/backend/``,这个函数让我们识别"已经是 backend 根"的情况。
pub(super) fn directory_if_contains(path: &Path, child: &str) -> Option<PathBuf> {
    if path.join(child).is_dir() {
        Some(path.to_path_buf())
    } else {
        None
    }
}

/// 在候选 ``Option<PathBuf>`` 列表中找第一个**存在的目录**。
pub(super) fn first_existing_dir<I>(items: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = Option<PathBuf>>,
{
    items
        .into_iter()
        .flatten()
        .find(|candidate| candidate.is_dir())
}

/// 在候选 ``Option<PathBuf>`` 列表中找第一个**存在的文件或目录**。
///
/// 与 ``first_existing_dir`` 区分:``ffmpeg`` / ``python`` 这种二进制走 file 路径,
/// ``models`` / ``runtime_root`` 这种走 dir。
pub(super) fn first_existing_file<I>(items: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = Option<PathBuf>>,
{
    items
        .into_iter()
        .flatten()
        .find(|candidate| candidate.exists())
}

/// 在 ``PATH`` 中查找可执行文件(Windows 会同时尝试 ``.exe`` 后缀)。
pub(super) fn find_in_system_path(executable: &str) -> Option<PathBuf> {
    let path_env = env::var_os("PATH")?;
    for dir in env::split_paths(&path_env) {
        let candidate = dir.join(executable);
        if candidate.is_file() {
            return Some(candidate);
        }
        #[cfg(target_os = "windows")]
        {
            if !executable.ends_with(".exe") {
                let candidate_exe = dir.join(format!("{executable}.exe"));
                if candidate_exe.is_file() {
                    return Some(candidate_exe);
                }
            }
        }
    }
    None
}

/// 平台对应的 Python 可执行文件名(Windows: ``python.exe``,其它: ``python3``)。
pub(super) fn platform_python_binary() -> &'static str {
    if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "python3"
    }
}

/// 平台对应的二进制文件名 — 仅识别 ffmpeg/ffprobe;其它名字原样返回。
pub(super) fn platform_binary(base: &'static str) -> &'static str {
    if cfg!(target_os = "windows") {
        match base {
            "ffmpeg" => "ffmpeg.exe",
            "ffprobe" => "ffprobe.exe",
            other => other,
        }
    } else {
        base
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_first_existing_dir() {
        let current = std::env::current_dir().expect("current dir");
        let selected = first_existing_dir([Some(PathBuf::from("missing")), Some(current.clone())]);
        assert_eq!(selected, Some(current));
    }

    #[test]
    fn selects_first_existing_file() {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml");
        let selected =
            first_existing_file([Some(PathBuf::from("missing")), Some(manifest.clone())]);
        assert_eq!(selected, Some(manifest));
    }

    #[test]
    fn directory_if_contains_returns_some_when_child_exists() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        // ``src`` 必然存在于 src-tauri/ 下
        assert_eq!(
            directory_if_contains(&manifest_dir, "src"),
            Some(manifest_dir.clone())
        );
    }

    #[test]
    fn directory_if_contains_returns_none_for_missing_child() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        assert_eq!(directory_if_contains(&manifest_dir, "this-does-not-exist"), None);
    }

    #[test]
    fn platform_python_binary_picks_platform_default() {
        let name = platform_python_binary();
        if cfg!(target_os = "windows") {
            assert_eq!(name, "python.exe");
        } else {
            assert_eq!(name, "python3");
        }
    }

    #[test]
    fn platform_binary_maps_known_names_on_windows_only() {
        if cfg!(target_os = "windows") {
            assert_eq!(platform_binary("ffmpeg"), "ffmpeg.exe");
            assert_eq!(platform_binary("ffprobe"), "ffprobe.exe");
        } else {
            assert_eq!(platform_binary("ffmpeg"), "ffmpeg");
            assert_eq!(platform_binary("ffprobe"), "ffprobe");
        }
        // 未知名字总是原样
        assert_eq!(platform_binary("custom-tool"), "custom-tool");
    }
}
