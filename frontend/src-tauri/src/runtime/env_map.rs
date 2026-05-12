//! 后端子进程环境变量构造。
//!
//! ``build_env_map`` 是 ``tasks/builder.rs`` 与 ``tasks/runner.rs`` 直接调用的
//! 公共 API,所以在 ``runtime::mod`` 通过 ``pub use`` 重新导出,保持调用方
//! 路径不变。

use super::ResolvedRuntimePaths;

pub fn build_env_map(paths: &ResolvedRuntimePaths) -> Vec<(String, String)> {
    let mut envs = vec![
        ("PYTHONIOENCODING".to_string(), "utf-8".to_string()),
        ("PYTHONUTF8".to_string(), "1".to_string()),
        (
            "VP_PYTHON_EXECUTABLE".to_string(),
            paths.python_executable.to_string_lossy().to_string(),
        ),
        (
            "VP_OUTPUT_DIR".to_string(),
            paths.output_dir.to_string_lossy().to_string(),
        ),
    ];

    if let Some(ffmpeg_path) = &paths.ffmpeg_path {
        envs.push((
            "VP_FFMPEG_PATH".to_string(),
            ffmpeg_path.to_string_lossy().to_string(),
        ));
    }

    if let Some(ffprobe_path) = &paths.ffprobe_path {
        envs.push((
            "VP_FFPROBE_PATH".to_string(),
            ffprobe_path.to_string_lossy().to_string(),
        ));
    }

    if let Some(model_dir) = &paths.model_dir {
        envs.push((
            "VP_RIFE_MODEL_DIR".to_string(),
            model_dir.to_string_lossy().to_string(),
        ));
    }

    // 优先透传系统环境变量中的 VP_TENSORRT_DIR(用户可能直接设了),
    // 即使 resolve_runtime_paths 没找到本地目录,也要让后端有机会读取。
    if let Some(tensorrt_dir) = &paths.tensorrt_dir {
        envs.push((
            "VP_TENSORRT_DIR".to_string(),
            tensorrt_dir.to_string_lossy().to_string(),
        ));
    } else if let Ok(trt_env) = std::env::var("VP_TENSORRT_DIR") {
        if !trt_env.is_empty() {
            envs.push(("VP_TENSORRT_DIR".to_string(), trt_env));
        }
    }

    if let Some(runtime_root) = &paths.runtime_root {
        envs.push((
            "VP_RUNTIME_ROOT".to_string(),
            runtime_root.to_string_lossy().to_string(),
        ));
    }

    envs.push((
        "VP_LOG_DIR".to_string(),
        paths.log_dir.to_string_lossy().to_string(),
    ));

    envs
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn excludes_legacy_temp_override() {
        let envs = build_env_map(&ResolvedRuntimePaths {
            backend_dir: PathBuf::from("backend"),
            runtime_root: Some(PathBuf::from("runtime")),
            python_executable: PathBuf::from("python"),
            ffmpeg_path: Some(PathBuf::from("ffmpeg")),
            ffprobe_path: Some(PathBuf::from("ffprobe")),
            model_dir: Some(PathBuf::from("models")),
            tensorrt_dir: None,
            output_dir: PathBuf::from("output"),
            log_dir: PathBuf::from("logs"),
        });
        let legacy_temp_key = ["VP", "TEMP", "DIR"].join("_");

        assert!(envs.iter().any(|(key, _)| key == "VP_OUTPUT_DIR"));
        assert!(envs
            .iter()
            .any(|(key, value)| key == "VP_PYTHON_EXECUTABLE" && value == "python"));
        assert!(!envs.iter().any(|(key, _)| key == &legacy_temp_key));
        assert!(!envs.iter().any(|(key, _)| key == "VP_TENSORRT_DIR"));
    }

    #[test]
    fn passes_tensorrt_dir_when_resolved() {
        let envs = build_env_map(&ResolvedRuntimePaths {
            backend_dir: PathBuf::from("backend"),
            runtime_root: None,
            python_executable: PathBuf::from("python"),
            ffmpeg_path: None,
            ffprobe_path: None,
            model_dir: None,
            tensorrt_dir: Some(PathBuf::from("D:\\TensorRT-10.14.1.48")),
            output_dir: PathBuf::from("output"),
            log_dir: PathBuf::from("logs"),
        });
        assert!(envs
            .iter()
            .any(|(key, value)| key == "VP_TENSORRT_DIR" && value == "D:\\TensorRT-10.14.1.48"));
    }
}
