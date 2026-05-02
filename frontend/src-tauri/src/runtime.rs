use std::env;
use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager, Runtime};

#[derive(Debug, Clone)]
pub struct ResolvedRuntimePaths {
    pub backend_dir: PathBuf,
    pub runtime_root: Option<PathBuf>,
    pub python_executable: PathBuf,
    pub ffmpeg_path: Option<PathBuf>,
    pub ffprobe_path: Option<PathBuf>,
    pub model_dir: Option<PathBuf>,
    pub tensorrt_dir: Option<PathBuf>,
    pub output_dir: PathBuf,
    pub log_dir: PathBuf,
}

pub fn resolve_runtime_paths<R: Runtime>(
    app: &AppHandle<R>,
) -> Result<ResolvedRuntimePaths, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let frontend_dir = manifest_dir
        .parent()
        .ok_or_else(|| "Unable to resolve frontend directory.".to_string())?
        .to_path_buf();
    let workspace_root = frontend_dir
        .parent()
        .ok_or_else(|| "Unable to resolve workspace root.".to_string())?
        .to_path_buf();
    let resource_dir = app.path().resource_dir().ok();

    let resource_backend = resource_dir.as_ref().and_then(|path| {
        directory_if_contains(path, "app")
            .or_else(|| Some(path.join("backend")).filter(|p| p.is_dir()))
    });

    let dev_backend_dir = if cfg!(debug_assertions) {
        Some(workspace_root.join("backend"))
    } else {
        None
    };
    let backend_dir = first_existing_dir([
        env_path("VP_BACKEND_DIR"),
        resource_backend,
        dev_backend_dir,
    ])
    .ok_or_else(|| "Unable to locate backend directory.".to_string())?;

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
    let runtime_root = first_existing_dir([
        env_path("VP_RUNTIME_ROOT"),
        resource_dir
            .as_ref()
            .map(|path| path.join("resources").join("runtime")),
        resource_dir.as_ref().map(|path| path.join("runtime")),
        dev_runtime_root,
    ]);

    let python_executable = match first_existing_file([
        env_path("VP_PYTHON_EXECUTABLE"),
        runtime_root
            .as_ref()
            .map(|path| path.join("python").join(platform_python_binary())),
        runtime_root.as_ref().map(|path| path.join("bin").join(platform_python_binary())),
        runtime_root
            .as_ref()
            .map(|path| path.join(platform_python_binary())),
    ]) {
        Some(path) => path,
        None => match find_in_system_path(platform_python_binary()) {
            Some(path) => path,
            None => {
                return Err(
                    "Python executable not found. Set VP_PYTHON_EXECUTABLE, install Python in your system PATH, or bundle resources/runtime/python/."
                        .to_string(),
                )
            }
        },
    };

    let ffmpeg_path = first_existing_file([
        env_path("VP_FFMPEG_PATH"),
        runtime_root.as_ref().map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffmpeg"))
        }),
        resource_dir.as_ref().map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffmpeg"))
        }),
    ]);

    let ffprobe_path = first_existing_file([
        env_path("VP_FFPROBE_PATH"),
        runtime_root.as_ref().map(|path| {
            path.join("ffmpeg")
                .join("bin")
                .join(platform_binary("ffprobe"))
        }),
        resource_dir.as_ref().map(|path| {
            path.join("ffprobe")
                .join("bin")
                .join(platform_binary("ffprobe"))
        }),
    ]);

    let dev_model_dir = if cfg!(debug_assertions) {
        Some(workspace_root.join("backend").join("models"))
    } else {
        None
    };
    let model_dir = first_existing_dir([
        env_path("VP_RIFE_MODEL_DIR"),
        runtime_root.as_ref().map(|path| path.join("models")),
        resource_dir.as_ref().map(|path| path.join("models")),
        resource_dir
            .as_ref()
            .map(|path| path.join("backend").join("models")),
        dev_model_dir,
    ]);

    let tensorrt_dir = first_existing_dir([
        env_path("VP_TENSORRT_DIR"),
        runtime_root.as_ref().map(|path| path.join("tensorrt")),
        resource_dir.as_ref().map(|path| path.join("tensorrt")),
    ]);

    if !cfg!(debug_assertions) {
        if ffmpeg_path.is_none() {
            return Err(
                "Bundled FFmpeg is missing. Set VP_FFMPEG_PATH or include resources/runtime/ffmpeg/bin/ffmpeg.exe."
                    .to_string(),
            );
        }
        if ffprobe_path.is_none() {
            return Err(
                "Bundled FFprobe is missing. Set VP_FFPROBE_PATH or include resources/runtime/ffmpeg/bin/ffprobe.exe."
                    .to_string(),
            );
        }
        let has_default_model = model_dir
            .as_ref()
            .map(|path| path.join(default_rife_model_file()).is_file())
            .unwrap_or(false);
        if !has_default_model {
            return Err(format!(
                "Bundled RIFE model is missing. Set VP_RIFE_MODEL_DIR or include resources/runtime/models/{}.",
                default_rife_model_file()
            ));
        }
    }

    let app_data_dir = app
        .path()
        .app_local_data_dir()
        .unwrap_or_else(|_| workspace_root.join(".tmp").join("app-data"));

    let output_dir = app_data_dir.join("output");
    let log_dir = app_data_dir.join("logs");

    std::fs::create_dir_all(&output_dir)
        .map_err(|error| format!("Unable to create output directory: {error}"))?;
    std::fs::create_dir_all(&log_dir)
        .map_err(|error| format!("Unable to create log directory: {error}"))?;

    Ok(ResolvedRuntimePaths {
        backend_dir,
        runtime_root,
        python_executable,
        ffmpeg_path,
        ffprobe_path,
        model_dir,
        tensorrt_dir,
        output_dir,
        log_dir,
    })
}

fn env_path(key: &str) -> Option<PathBuf> {
    env::var_os(key).map(PathBuf::from)
}

fn directory_if_contains(path: &Path, child: &str) -> Option<PathBuf> {
    if path.join(child).is_dir() {
        Some(path.to_path_buf())
    } else {
        None
    }
}

fn first_existing_dir<I>(items: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = Option<PathBuf>>,
{
    items
        .into_iter()
        .flatten()
        .find(|candidate| candidate.is_dir())
}

fn first_existing_file<I>(items: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = Option<PathBuf>>,
{
    items
        .into_iter()
        .flatten()
        .find(|candidate| candidate.exists())
}

fn find_in_system_path(executable: &str) -> Option<PathBuf> {
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

fn default_rife_model_file() -> &'static str {
    "flownet_v4.25.pkl"
}

pub fn platform_python_binary() -> &'static str {
    if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "python3"
    }
}

pub fn platform_binary(base: &'static str) -> &'static str {
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

    if let Some(tensorrt_dir) = &paths.tensorrt_dir {
        envs.push((
            "VP_TENSORRT_DIR".to_string(),
            tensorrt_dir.to_string_lossy().to_string(),
        ));
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
    use super::{build_env_map, first_existing_dir, first_existing_file, ResolvedRuntimePaths};
    use std::path::PathBuf;

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
    fn build_env_map_excludes_legacy_temp_override() {
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
    fn build_env_map_passes_tensorrt_dir_when_resolved() {
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
