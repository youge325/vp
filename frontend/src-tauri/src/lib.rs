mod models;
mod runtime;
mod tasks;

use std::path::PathBuf;

use models::TaskState;
use rfd::FileDialog;
use tauri::{AppHandle, Emitter, Manager, Runtime, State};

use crate::runtime::resolve_runtime_paths;

#[tauri::command]
async fn pick_input() -> Result<Option<String>, String> {
    Ok(FileDialog::new()
        .set_title("选择输入视频")
        .add_filter("Video", &["mp4", "avi", "mkv", "mov", "flv", "webm", "wmv"])
        .pick_file()
        .map(|path| path.display().to_string()))
}

#[tauri::command]
async fn pick_output(file_name: Option<String>) -> Result<Option<String>, String> {
    let mut dialog = FileDialog::new();
    dialog = dialog.set_title("选择输出文件");

    if let Some(file_name) = file_name {
        dialog = dialog.set_file_name(&file_name);
    }

    Ok(dialog
        .add_filter("Video", &["mp4", "avi", "mkv", "mov"])
        .save_file()
        .map(|path| path.display().to_string()))
}

#[tauri::command]
async fn check_environment<R: Runtime>(app: AppHandle<R>) -> Result<serde_json::Value, String> {
    tasks::run_single_cli_command(&app, &[String::from("check")]).await
}

#[tauri::command]
async fn inspect_video<R: Runtime>(
    app: AppHandle<R>,
    input_path: String,
) -> Result<serde_json::Value, String> {
    tasks::run_single_cli_command(
        &app,
        &[String::from("info"), String::from("--input"), input_path],
    )
    .await
}

#[tauri::command]
async fn start_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    request: models::TaskRequest,
) -> Result<(), String> {
    tasks::spawn_task(app, state, request).await
}

#[tauri::command]
async fn cancel_task(state: State<'_, TaskState>) -> Result<(), String> {
    tasks::cancel_running_task(state).await
}

#[tauri::command]
async fn open_output_location(path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(path);
    let target = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf
            .parent()
            .map(PathBuf::from)
            .unwrap_or(path_buf)
    };

    open::that_detached(target).map_err(|error| format!("Unable to open output location: {error}"))
}

#[tauri::command]
async fn open_file_or_directory(path: String) -> Result<(), String> {
    open::that_detached(path).map_err(|error| format!("Unable to open path: {error}"))
}

#[tauri::command]
async fn resolved_runtime<R: Runtime>(app: AppHandle<R>) -> Result<serde_json::Value, String> {
    let paths = resolve_runtime_paths(&app)?;
    serde_json::to_value(serde_json::json!({
        "backendDir": paths.backend_dir,
        "runtimeRoot": paths.runtime_root,
        "pythonExecutable": paths.python_executable,
        "ffmpegPath": paths.ffmpeg_path,
        "ffprobePath": paths.ffprobe_path,
        "modelDir": paths.model_dir,
        "outputDir": paths.output_dir,
        "tempDir": paths.temp_dir,
        "runtimeMode": paths.runtime_mode,
        "bundled": paths.bundled
    }))
    .map_err(|error| format!("Unable to serialize runtime paths: {error}"))
}

pub fn run() {
    tauri::Builder::default()
        .manage(TaskState::default())
        .setup(|app| {
            let app_handle = app.handle();
            let _ = resolve_runtime_paths(&app_handle);

            if let Some(resource_dir) = app_handle.path().resource_dir().ok() {
                let _ = app_handle.emit(
                    "task-log",
                    models::TaskLogPayload {
                        message: format!("resource-dir={}", resource_dir.display()),
                    },
                );
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            pick_input,
            pick_output,
            check_environment,
            inspect_video,
            start_task,
            cancel_task,
            open_output_location,
            open_file_or_directory,
            resolved_runtime
        ])
        .run(tauri::generate_context!())
        .expect("error while running VP Workbench");
}
