pub mod models;
pub mod protocol;
mod persistence;
mod process_control;
mod runtime;
mod services;
mod tasks;

use std::path::PathBuf;

use models::TaskState;
use rfd::FileDialog;
use tauri::{AppHandle, Emitter, Manager, Runtime, State};

use crate::runtime::resolve_runtime_paths;

#[tauri::command]
async fn pick_inputs() -> Result<Vec<String>, String> {
    Ok(FileDialog::new()
        .set_title("Import Videos")
        .add_filter(
            "Video",
            &["mp4", "avi", "mkv", "mov", "flv", "webm", "wmv", "ts"],
        )
        .pick_files()
        .unwrap_or_default()
        .into_iter()
        .map(|path| path.display().to_string())
        .collect())
}

#[tauri::command]
async fn pick_output_directory() -> Result<Option<String>, String> {
    Ok(FileDialog::new()
        .set_title("Select Output Directory")
        .pick_folder()
        .map(|path| path.display().to_string()))
}

#[tauri::command]
#[allow(non_snake_case)]
async fn check_environment<R: Runtime>(
    app: AppHandle<R>,
    forceRefresh: bool,
) -> Result<models::EnvironmentCheckPayload, String> {
    services::environment_service::check_environment(app, forceRefresh).await
}

#[tauri::command]
async fn load_workbench_preset<R: Runtime>(
    app: AppHandle<R>,
) -> Result<Option<models::WorkbenchPreset>, String> {
    let data_dir = persistence::app_data_dir(&app)?;
    Ok(persistence::load_workbench_preset(&data_dir))
}

#[tauri::command]
async fn save_workbench_preset<R: Runtime>(
    app: AppHandle<R>,
    preset: models::WorkbenchPreset,
) -> Result<(), String> {
    let data_dir = persistence::app_data_dir(&app)?;
    persistence::save_workbench_preset(&data_dir, &preset)
}

#[tauri::command]
async fn inspect_video<R: Runtime>(
    app: AppHandle<R>,
    input_path: String,
) -> Result<models::VideoInfo, String> {
    let raw = tasks::run_single_cli_command(
        &app,
        &[String::from("info"), String::from("--input"), input_path],
    )
    .await?;
    serde_json::from_value::<models::VideoInfo>(raw)
        .map_err(|error| format!("Unable to deserialize video info: {error}"))
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
async fn check_resume_state<R: Runtime>(
    app: AppHandle<R>,
    request: models::TaskRequest,
) -> Result<serde_json::Value, String> {
    let args = tasks::build_inspect_output_args(&request)
        .map_err(|error| format!("Unable to build resume inspection args: {error}"))?;
    tasks::run_single_cli_command(&app, &args).await
}

#[tauri::command]
async fn cancel_task(state: State<'_, TaskState>) -> Result<(), String> {
    tasks::cancel_running_task(state).await
}

#[tauri::command]
async fn pause_task(state: State<'_, TaskState>) -> Result<(), String> {
    tasks::pause_running_task(state).await
}

#[tauri::command]
async fn resume_task(state: State<'_, TaskState>) -> Result<(), String> {
    tasks::resume_running_task(state).await
}

#[tauri::command]
async fn open_output_location(path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(path);
    let target = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf.parent().map(PathBuf::from).unwrap_or(path_buf)
    };
    open::that_detached(target).map_err(|error| format!("Unable to open output location: {error}"))
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
            pick_inputs,
            pick_output_directory,
            check_environment,
            load_workbench_preset,
            save_workbench_preset,
            inspect_video,
            check_resume_state,
            start_task,
            cancel_task,
            pause_task,
            resume_task,
            open_output_location
        ])
        .run(tauri::generate_context!())
        .expect("error while running VP Workbench");
}

#[cfg(test)]
mod tests {
    const DEFAULT_PERMISSIONS: &str = include_str!("../permissions/default.toml");
    const ACL_MANIFESTS: &str = include_str!("../gen/schemas/acl-manifests.json");

    #[test]
    fn default_permissions_include_active_desktop_commands() {
        assert!(DEFAULT_PERMISSIONS.contains("allow-pick-inputs"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-pick-output-directory"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-load-workbench-preset"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-save-workbench-preset"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-check-resume-state"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-start-task"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-cancel-task"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-pause-task"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-resume-task"));
        assert!(DEFAULT_PERMISSIONS.contains("allow-open-output-location"));
    }

    #[test]
    fn default_permissions_exclude_removed_legacy_commands() {
        assert!(!DEFAULT_PERMISSIONS
            .lines()
            .any(|line| line.trim() == "\"allow-pick-input\","));
        assert!(!DEFAULT_PERMISSIONS
            .lines()
            .any(|line| line.trim() == "\"allow-pick-output\","));
        assert!(!DEFAULT_PERMISSIONS
            .lines()
            .any(|line| line.trim() == "\"allow-open-file-or-directory\","));
        assert!(!DEFAULT_PERMISSIONS
            .lines()
            .any(|line| line.trim() == "\"allow-resolved-runtime\","));
    }

    #[test]
    fn generated_acl_manifest_tracks_active_commands_only() {
        assert!(ACL_MANIFESTS.contains("allow-pick-inputs"));
        assert!(ACL_MANIFESTS.contains("allow-pick-output-directory"));
        assert!(ACL_MANIFESTS.contains("allow-load-workbench-preset"));
        assert!(ACL_MANIFESTS.contains("allow-save-workbench-preset"));
        assert!(ACL_MANIFESTS.contains("allow-check-resume-state"));
        assert!(ACL_MANIFESTS.contains("allow-start-task"));
        assert!(ACL_MANIFESTS.contains("allow-cancel-task"));
        assert!(ACL_MANIFESTS.contains("allow-pause-task"));
        assert!(ACL_MANIFESTS.contains("allow-resume-task"));
        assert!(!ACL_MANIFESTS.contains("\"allow-pick-output\""));
        assert!(!ACL_MANIFESTS.contains("\"allow-open-file-or-directory\""));
        assert!(!ACL_MANIFESTS.contains("\"allow-resolved-runtime\""));
    }
}
