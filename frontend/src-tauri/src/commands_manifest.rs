// Single declaration of the Tauri command set.
//
// Phase C.2.4 collapsed the duplicated command-name lists that used to live
// in ``build.rs::APP_COMMANDS`` and the various ``lib.rs::tests`` string
// assertions. Now both compile units pull this file:
//
// - ``build.rs`` via ``include!("src/commands_manifest.rs")`` — because a
//   build script is a separate binary it cannot ``use`` the lib crate's
//   modules, so we treat this file as a snippet of bare constants. The
//   snippet is inlined into the build script's main module, so this file
//   must NOT use ``//!`` inner doc comments (they would land inside
//   ``fn main`` and trip ``E0753``).
// - ``src/lib.rs`` via ``mod commands_manifest;`` — exposes
//   ``APP_COMMAND_NAMES`` as a regular constant for tests.
//
// Adding a new ``#[tauri::command]`` means:
//   1. Implement the function in its sub-module.
//   2. Append its name to ``APP_COMMAND_NAMES`` below.
//   3. Register it in ``tauri::generate_handler![...]`` inside ``lib.rs``.
//
// The integration test in ``lib.rs::tests`` then verifies that every name
// in ``APP_COMMAND_NAMES`` is also present in ``permissions/default.toml``
// and ``gen/schemas/acl-manifests.json`` — a single source of truth check.

pub const APP_COMMAND_NAMES: &[&str] = &[
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
