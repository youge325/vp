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
    pub output_dir: PathBuf,
    pub temp_dir: PathBuf,
    pub runtime_mode: String,
    pub bundled: bool,
}

pub fn resolve_runtime_paths<R: Runtime>(app: &AppHandle<R>) -> Result<ResolvedRuntimePaths, String> {
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

    let backend_dir = first_existing_dir([
        env_path("VP_BACKEND_DIR"),
        resource_dir
            .as_ref()
            .and_then(|path| directory_if_contains(path, "app")),
        resource_dir.as_ref().map(|path| path.join("backend")),
        Some(workspace_root.join("backend")),
    ])
    .ok_or_else(|| "Unable to locate backend directory.".to_string())?;

    let runtime_root = first_existing_dir([
        env_path("VP_RUNTIME_ROOT"),
        resource_dir.as_ref().map(|path| path.join("resources").join("runtime")),
        resource_dir.as_ref().map(|path| path.join("runtime")),
        Some(frontend_dir.join("src-tauri").join("resources").join("runtime")),
    ]);

    let bundled = runtime_root.is_some();
    let runtime_mode = if bundled {
        "bundled".to_string()
    } else {
        "workspace".to_string()
    };

    let python_executable = first_existing_file([
        env_path("VP_PYTHON_EXECUTABLE"),
        runtime_root
            .as_ref()
            .map(|path| path.join("python").join(platform_python_binary())),
        runtime_root.as_ref().map(|path| path.join("bin").join(platform_python_binary())),
        runtime_root
            .as_ref()
            .map(|path| path.join(platform_python_binary())),
    ])
    .unwrap_or_else(|| PathBuf::from(platform_python_binary()));

    let ffmpeg_path = first_existing_file([
        env_path("VP_FFMPEG_PATH"),
        runtime_root
            .as_ref()
            .map(|path| path.join("ffmpeg").join("bin").join(platform_binary("ffmpeg"))),
        resource_dir
            .as_ref()
            .map(|path| path.join("ffmpeg").join("bin").join(platform_binary("ffmpeg"))),
    ]);

    let ffprobe_path = first_existing_file([
        env_path("VP_FFPROBE_PATH"),
        runtime_root
            .as_ref()
            .map(|path| path.join("ffmpeg").join("bin").join(platform_binary("ffprobe"))),
        resource_dir
            .as_ref()
            .map(|path| path.join("ffprobe").join("bin").join(platform_binary("ffprobe"))),
    ]);

    let model_dir = first_existing_dir([
        env_path("VP_RIFE_MODEL_DIR"),
        runtime_root.as_ref().map(|path| path.join("models")),
        resource_dir.as_ref().map(|path| path.join("models")),
        resource_dir.as_ref().map(|path| path.join("backend").join("models")),
        Some(workspace_root.join("backend").join("models")),
    ]);

    let output_dir = app
        .path()
        .app_local_data_dir()
        .unwrap_or_else(|_| workspace_root.join(".tmp").join("app-output"))
        .join("output");
    let temp_dir = app
        .path()
        .app_cache_dir()
        .unwrap_or_else(|_| workspace_root.join(".tmp").join("app-cache"))
        .join("temp");

    std::fs::create_dir_all(&output_dir)
        .map_err(|error| format!("Unable to create output directory: {error}"))?;
    std::fs::create_dir_all(&temp_dir)
        .map_err(|error| format!("Unable to create temp directory: {error}"))?;

    Ok(ResolvedRuntimePaths {
        backend_dir,
        runtime_root,
        python_executable,
        ffmpeg_path,
        ffprobe_path,
        model_dir,
        output_dir,
        temp_dir,
        runtime_mode,
        bundled,
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
            "VP_OUTPUT_DIR".to_string(),
            paths.output_dir.to_string_lossy().to_string(),
        ),
        (
            "VP_TEMP_DIR".to_string(),
            paths.temp_dir.to_string_lossy().to_string(),
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

    if let Some(runtime_root) = &paths.runtime_root {
        envs.push((
            "VP_RUNTIME_ROOT".to_string(),
            runtime_root.to_string_lossy().to_string(),
        ));
    }

    envs
}

#[cfg(test)]
mod tests {
    use super::{first_existing_dir, first_existing_file};
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
        let selected = first_existing_file([Some(PathBuf::from("missing")), Some(manifest.clone())]);
        assert_eq!(selected, Some(manifest));
    }
}
