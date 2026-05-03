const APP_COMMANDS: &[&str] = &[
    "pick_inputs",
    "pick_output_directory",
    "check_environment",
    "load_workbench_preset",
    "save_workbench_preset",
    "inspect_video",
    "check_resume_state",
    "start_task",
    "cancel_task",
    "pause_task",
    "resume_task",
    "open_output_location",
];

fn main() {
    let attributes = tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(APP_COMMANDS));

    tauri_build::try_build(attributes).expect("failed to run tauri-build");
}
