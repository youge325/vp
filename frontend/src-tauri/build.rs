const APP_COMMANDS: &[&str] = &[
    "pick_input",
    "pick_output",
    "check_environment",
    "inspect_video",
    "start_task",
    "cancel_task",
    "open_output_location",
    "open_file_or_directory",
    "resolved_runtime",
];

fn main() {
    let attributes = tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(APP_COMMANDS));

    tauri_build::try_build(attributes).expect("failed to run tauri-build");
}
