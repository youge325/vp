mod commands_manifest;
mod dialogs;
mod error;
pub mod models;
mod persistence;
mod process_control;
mod protocol;
mod runtime;
mod services;
mod tasks;

use std::error::Error as StdError;

use tauri::{Manager, PhysicalPosition, PhysicalSize};

use crate::runtime::resolve_runtime_paths;
use crate::tasks::TaskState;

fn is_e2e_headless() -> bool {
    std::env::var("VP_E2E_HEADLESS").is_ok()
        || std::env::args().any(|arg| arg == "--vp-e2e-headless")
}

pub fn run() {
    let result = tauri::Builder::default()
        .manage(TaskState::default())
        .setup(|app| {
            let app_handle = app.handle();
            // Phase D.1.4 — surface runtime-resolution failures instead of
            // dropping them on the floor. Without ffmpeg / a Python runtime
            // every invoke would later fail with a generic error; aborting
            // setup gives the user a single clear startup error.
            //
            // Phase D.3.6 — resolve once at startup and stash the result in
            // managed state. Previous code re-ran ``resolve_runtime_paths``
            // (which does ~10 filesystem stats) inside every Tauri command.
            let paths = match resolve_runtime_paths(app_handle) {
                Ok(paths) => paths,
                Err(error) => {
                    eprintln!("VP Workbench failed to resolve runtime paths: {error}");
                    return Err(Box::new(error) as Box<dyn StdError>);
                }
            };
            app.manage(paths);

            if let Ok(resource_dir) = app_handle.path().resource_dir() {
                // Was previously an Emitter call that fired before any
                // frontend listener could be attached — make it a stderr
                // breadcrumb so it survives into release-build console logs.
                eprintln!("VP Workbench resource-dir={}", resource_dir.display());
            }

            // tauri.conf.json keeps the window hidden initially. In E2E mode,
            // WebDriver/WebView2 may still request focus later, so park the
            // window off-screen before keeping it hidden.
            if let Some(window) = app.get_webview_window("main") {
                if is_e2e_headless() {
                    let _ = window.set_skip_taskbar(true);
                    let _ = window.set_size(PhysicalSize::new(1280, 860));
                    let _ = window.set_position(PhysicalPosition::new(-32000, -32000));
                    let _ = window.show();
                } else {
                    let _ = window.set_focusable(true);
                    let _ = window.set_skip_taskbar(false);
                    let _ = window.center();
                    let _ = window.show();
                }
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
            tasks::commands::control_task,
            persistence::commands::load_workbench_preset,
            persistence::commands::save_workbench_preset,
        ])
        .run(tauri::generate_context!());

    if let Err(error) = result {
        eprintln!("VP Workbench exited with a fatal error: {error}");
        std::process::exit(1);
    }
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
            // Phase A — pause_task / resume_task 合并为 control_task,
            // 旧 token 必须从 default.toml 中清除。
            "\"allow-pause-task\",",
            "\"allow-resume-task\",",
        ];
        for token in legacy {
            assert!(
                !DEFAULT_PERMISSIONS.lines().any(|line| line.trim() == token),
                "permissions/default.toml still mentions legacy `{token}`",
            );
        }
    }
}
