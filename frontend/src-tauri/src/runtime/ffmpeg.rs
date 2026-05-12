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

use std::path::PathBuf;

use super::helpers::{env_path, first_existing_file, platform_binary};

pub(super) fn resolve_ffmpeg_path(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
) -> Option<PathBuf> {
    first_existing_file([
        env_path("VP_FFMPEG_PATH"),
        runtime_root.map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffmpeg"))
        }),
        resource_dir.map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffmpeg"))
        }),
    ])
}

pub(super) fn resolve_ffprobe_path(
    runtime_root: Option<&PathBuf>,
    resource_dir: Option<&PathBuf>,
) -> Option<PathBuf> {
    first_existing_file([
        env_path("VP_FFPROBE_PATH"),
        runtime_root.map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffprobe"))
        }),
        // 历史遗留:resource_dir 下旧布局是 ``ffprobe/bin/ffprobe.exe``,与 ffmpeg
        // 不同——保持现状以兼容旧 bundle。
        resource_dir.map(|path| {
            path.join("ffprobe")
                .join("bin")
                .join(platform_binary("ffprobe"))
        }),
    ])
}
