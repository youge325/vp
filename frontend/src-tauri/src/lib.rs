pub mod models;
pub mod protocol;
pub mod error;
mod persistence;
mod process_control;
mod runtime;
mod services;
mod tasks;

use std::path::PathBuf;

use rfd::FileDialog;
use tauri::{AppHandle, Emitter, Manager, Runtime};

use crate::error::ShellError;
use crate::runtime::resolve_runtime_paths;
use crate::tasks::TaskState;

// ------------------------------------------------------------------
// Desktop-shell native commands (genuinely belong in lib.rs)
// ------------------------------------------------------------------

#[tauri::command]
async fn pick_inputs() -> Result<Vec<String>, ShellError> {
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
async fn pick_output_directory() -> Result<Option<String>, ShellError> {
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
) -> Result<models::EnvironmentCheckPayload, ShellError> {
    services::environment_service::check_environment(app, forceRefresh).await
}

#[tauri::command]
async fn open_output_location(path: String) -> Result<(), ShellError> {
    let path_buf = PathBuf::from(path);
    let target = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf.parent().map(PathBuf::from).unwrap_or(path_buf)
    };
    open::that_detached(target).map_err(|error| {
        ShellError::Io(std::io::Error::new(
            std::io::ErrorKind::Other,
            format!("Unable to open output location: {error}"),
        ))
    })
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
            open_output_location,
            // Task commands (sunk to tasks::commands)
            tasks::commands::inspect_video,
            tasks::commands::start_task,
            tasks::commands::check_resume_state,
            tasks::commands::cancel_task,
            tasks::commands::pause_task,
            tasks::commands::resume_task,
            // Persistence commands (sunk to persistence::commands)
            persistence::commands::load_workbench_preset,
            persistence::commands::save_workbench_preset,
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
    }
}
