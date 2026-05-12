pub mod models;
pub mod protocol;
pub mod error;
mod commands_manifest;
mod dialogs;
mod persistence;
mod process_control;
mod runtime;
mod services;
mod tasks;

use tauri::{Emitter, Manager};

use crate::runtime::resolve_runtime_paths;
use crate::tasks::TaskState;

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
            dialogs::pick_inputs,
            dialogs::pick_output_directory,
            dialogs::open_output_location,
            services::environment_service::check_environment,
            tasks::commands::inspect_video,
            tasks::commands::start_task,
            tasks::commands::check_resume_state,
            tasks::commands::cancel_task,
            tasks::commands::pause_task,
            tasks::commands::resume_task,
            persistence::commands::load_workbench_preset,
            persistence::commands::save_workbench_preset,
        ])
        .run(tauri::generate_context!())
        .expect("error while running VP Workbench");
}

#[cfg(test)]
mod tests {
    use crate::commands_manifest::APP_COMMAND_NAMES;

    const DEFAULT_PERMISSIONS: &str = include_str!("../permissions/default.toml");
    const ACL_MANIFESTS: &str = include_str!("../gen/schemas/acl-manifests.json");

    fn allow_token(command_name: &str) -> String {
        format!("allow-{}", command_name.replace('_', "-"))
    }

    #[test]
    fn default_permissions_declare_every_command_in_manifest() {
        for command in APP_COMMAND_NAMES {
            let token = allow_token(command);
            assert!(
                DEFAULT_PERMISSIONS.contains(&token),
                "permissions/default.toml is missing `{token}` for command `{command}`",
            );
        }
    }

    #[test]
    fn generated_acl_manifest_matches_command_manifest() {
        for command in APP_COMMAND_NAMES {
            let token = allow_token(command);
            assert!(
                ACL_MANIFESTS.contains(&token),
                "gen/schemas/acl-manifests.json is missing `{token}` — try running `cargo build` to regenerate",
            );
        }
    }

    #[test]
    fn default_permissions_exclude_removed_legacy_commands() {
        // Stale tokens that pre-date Phase A; if they ever come back through
        // ACL generation it usually means a renamed command was added without
        // updating the manifest.
        let legacy = [
            "\"allow-pick-input\",",
            "\"allow-pick-output\",",
            "\"allow-open-file-or-directory\",",
            "\"allow-resolved-runtime\",",
        ];
        for token in legacy {
            assert!(
                !DEFAULT_PERMISSIONS.lines().any(|line| line.trim() == token),
                "permissions/default.toml still mentions legacy `{token}`",
            );
        }
    }
}
