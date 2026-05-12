//! Tauri build script.
//!
//! Pulls the canonical command list from ``src/commands_manifest.rs`` via
//! ``include!`` so that adding a new ``#[tauri::command]`` only requires
//! editing one file (the manifest), not two.

include!("src/commands_manifest.rs");

fn main() {
    let attributes = tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(APP_COMMAND_NAMES));

    tauri_build::try_build(attributes).expect("failed to run tauri-build");
}
