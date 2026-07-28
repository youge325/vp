//! Deterministic Tauri build integration.
//!
//! Cross-language generation and freshness checks run as explicit repository
//! gates. Cargo only consumes the already-generated neutral IPC manifest.

include!("src/generated/ipc_manifest.rs");

fn main() {
    let attributes = tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(APP_COMMAND_NAMES));
    tauri_build::try_build(attributes).expect("failed to run tauri-build");
}
