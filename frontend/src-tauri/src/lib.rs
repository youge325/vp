mod dialogs;
mod error;
mod generated;
pub mod models;
mod persistence;
mod process_control;
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
            // Resolve once and surface startup failures before any invoke.
            let paths = match resolve_runtime_paths(app_handle) {
                Ok(paths) => paths,
                Err(error) => {
                    eprintln!("VP Workbench failed to resolve runtime paths: {error}");
                    return Err(Box::new(error) as Box<dyn StdError>);
                }
            };
            app.manage(paths);

            if let Ok(resource_dir) = app_handle.path().resource_dir() {
                // Startup diagnostics use stderr because frontend listeners are
                // not attached during setup.
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
    include!("generated/ipc_manifest.rs");
    use std::collections::BTreeSet;

    const DEFAULT_PERMISSIONS: &str = include_str!("../permissions/default.toml");
    const ACL_MANIFESTS: &str = include_str!("../gen/schemas/acl-manifests.json");
    const DEFAULT_CAPABILITY: &str = include_str!("../capabilities/default.json");
    const TAURI_CONFIG: &str = include_str!("../tauri.conf.json");

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
    fn default_capability_is_local_only() {
        let capability: serde_json::Value =
            serde_json::from_str(DEFAULT_CAPABILITY).expect("valid capability JSON");
        assert_eq!(capability["local"], true);
        assert!(
            capability.get("remote").is_none(),
            "remote web origins must not receive desktop command permissions"
        );
        assert_eq!(capability["windows"], serde_json::json!(["main"]));
    }

    #[test]
    fn tauri_config_enables_only_the_local_capability_and_a_restrictive_csp() {
        let config: serde_json::Value =
            serde_json::from_str(TAURI_CONFIG).expect("valid Tauri config JSON");
        let security = &config["app"]["security"];
        assert_eq!(security["capabilities"], serde_json::json!(["default"]));
        let csp = security["csp"].as_str().expect("CSP string");
        for directive in [
            "script-src 'self'",
            "object-src 'none'",
            "frame-src 'none'",
            "base-uri 'self'",
        ] {
            assert!(csp.contains(directive), "CSP is missing `{directive}`");
        }
        assert!(!csp.contains("localhost:1420"));
        assert!(!csp.contains("127.0.0.1:1420"));
    }

    #[test]
    fn main_window_uses_native_dark_theme() {
        let config: serde_json::Value =
            serde_json::from_str(TAURI_CONFIG).expect("valid Tauri config JSON");
        let main_window = config["app"]["windows"]
            .as_array()
            .expect("window configuration array")
            .iter()
            .find(|window| window["label"] == "main")
            .expect("main window configuration");

        assert_eq!(main_window["theme"], "Dark");
        assert!(
            main_window
                .get("decorations")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(true),
            "the native title bar must remain enabled"
        );
    }

    #[test]
    fn command_manifest_contains_exactly_ten_unique_commands() {
        let unique = APP_COMMAND_NAMES.iter().copied().collect::<BTreeSet<_>>();

        assert_eq!(APP_COMMAND_NAMES.len(), 10);
        assert_eq!(unique.len(), APP_COMMAND_NAMES.len());
    }

    #[test]
    fn default_permission_tokens_exactly_match_the_command_manifest() {
        let expected = APP_COMMAND_NAMES
            .iter()
            .map(|command| allow_token(command))
            .collect::<BTreeSet<_>>();
        let actual = DEFAULT_PERMISSIONS
            .lines()
            .map(str::trim)
            .filter(|line| line.starts_with("\"allow-"))
            .map(|line| line.trim_matches(&['"', ','][..]).to_string())
            .collect::<BTreeSet<_>>();

        assert_eq!(actual, expected);
    }

    #[test]
    fn default_capability_grants_only_core_and_application_permissions() {
        let capability: serde_json::Value =
            serde_json::from_str(DEFAULT_CAPABILITY).expect("valid capability JSON");

        assert_eq!(capability["identifier"], "default");
        assert_eq!(
            capability["permissions"],
            serde_json::json!(["core:default", "default"])
        );
    }

    #[test]
    fn csp_connect_sources_are_limited_to_tauri_ipc() {
        let config: serde_json::Value =
            serde_json::from_str(TAURI_CONFIG).expect("valid Tauri config JSON");
        let csp = config["app"]["security"]["csp"]
            .as_str()
            .expect("CSP string");
        let connect = csp
            .split(';')
            .map(str::trim)
            .find(|directive| directive.starts_with("connect-src "))
            .expect("connect-src directive");

        assert_eq!(connect, "connect-src ipc: http://ipc.localhost");
        assert!(!connect.contains("https:"));
        assert!(!connect.contains("ws:"));
    }

    #[test]
    fn csp_script_object_and_frame_sources_are_exact() {
        let config: serde_json::Value =
            serde_json::from_str(TAURI_CONFIG).expect("valid Tauri config JSON");
        let csp = config["app"]["security"]["csp"]
            .as_str()
            .expect("CSP string");
        let directives = csp
            .split(';')
            .map(str::trim)
            .filter(|directive| !directive.is_empty())
            .collect::<BTreeSet<_>>();

        assert!(directives.contains("script-src 'self'"));
        assert!(directives.contains("object-src 'none'"));
        assert!(directives.contains("frame-src 'none'"));
        assert!(!csp.contains("'unsafe-eval'"));
    }
}
