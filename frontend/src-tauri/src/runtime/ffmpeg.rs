//! FFmpeg / FFprobe 路径解析。
//!
//! 三层探测,优先级从高到低:
//!   1. ``VP_FFMPEG_PATH`` / ``VP_FFPROBE_PATH`` 环境变量
//!   2. ``$RUNTIME_ROOT/ffmpeg/bin/ffmpeg.exe`` 等打包位置
//!   3. Tauri ``$RESOURCE/`` 下的 ffmpeg 子目录
//!
//! Release 构建中如果 1/2/3 都没命中,``mod.rs`` 会把 None 视为致命错误并返回
//! ``ShellError::RuntimeResolution`` — 见 ``resolve_runtime_paths`` 的 release
//! 必需性检查。Dev 构建允许 None,后端运行时会回退到自己探测。

use std::path::{Path, PathBuf};

use super::helpers::{env_path, first_existing_file, platform_binary};

pub(super) fn resolve_ffmpeg_tools(
    runtime_root: Option<&Path>,
    resource_dir: Option<&Path>,
) -> (Option<PathBuf>, Option<PathBuf>) {
    let ffmpeg = resolve_tool_path(
        env_path("VP_FFMPEG_PATH"),
        runtime_root,
        resource_dir,
        "ffmpeg",
    );
    let ffprobe = resolve_tool_path(
        env_path("VP_FFPROBE_PATH"),
        runtime_root,
        resource_dir,
        "ffprobe",
    );
    (ffmpeg, ffprobe)
}

fn resolve_tool_path(
    configured_path: Option<PathBuf>,
    runtime_root: Option<&Path>,
    resource_dir: Option<&Path>,
    binary: &'static str,
) -> Option<PathBuf> {
    first_existing_file([
        configured_path,
        runtime_root.map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary(binary))
        }),
        resource_dir.map(|path| {
            // Resources keep each tool in its own directory, including the
            // legacy ``ffprobe/bin/ffprobe`` layout.
            path.join(binary).join("bin").join(platform_binary(binary))
        }),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_tool(root: &Path, directory: &str, binary: &'static str) -> PathBuf {
        let path = root
            .join(directory)
            .join("bin")
            .join(platform_binary(binary));
        std::fs::create_dir_all(path.parent().expect("tool parent")).expect("create tool parent");
        std::fs::write(&path, b"tool").expect("write tool");
        path
    }

    #[test]
    fn tool_resolution_preserves_config_runtime_resource_priority() {
        let temp = tempfile::tempdir().expect("temp dir");
        let runtime_root = temp.path().join("runtime");
        let resource_dir = temp.path().join("resources");
        let configured = temp.path().join(platform_binary("ffmpeg"));
        std::fs::write(&configured, b"configured").expect("write configured tool");
        let runtime = create_tool(&runtime_root, "ffmpeg", "ffmpeg");
        let resource = create_tool(&resource_dir, "ffmpeg", "ffmpeg");

        assert_eq!(
            resolve_tool_path(
                Some(configured.clone()),
                Some(&runtime_root),
                Some(&resource_dir),
                "ffmpeg",
            ),
            Some(configured.clone())
        );

        std::fs::remove_file(&configured).expect("remove configured tool");
        assert_eq!(
            resolve_tool_path(
                Some(configured),
                Some(&runtime_root),
                Some(&resource_dir),
                "ffmpeg",
            ),
            Some(runtime.clone())
        );

        std::fs::remove_file(&runtime).expect("remove runtime tool");
        assert_eq!(
            resolve_tool_path(None, Some(&runtime_root), Some(&resource_dir), "ffmpeg",),
            Some(resource)
        );
    }

    #[test]
    fn ffprobe_resource_layout_remains_distinct_from_runtime_layout() {
        let temp = tempfile::tempdir().expect("temp dir");
        let runtime_root = temp.path().join("runtime");
        let resource_dir = temp.path().join("resources");
        let resource = create_tool(&resource_dir, "ffprobe", "ffprobe");

        assert_eq!(
            resolve_tool_path(None, Some(&runtime_root), Some(&resource_dir), "ffprobe",),
            Some(resource)
        );
    }
}
