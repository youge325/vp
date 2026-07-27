use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{ResumeInspectionResult, TaskRequest, VideoInfo};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{
    build_inspect_output_args, cancel_running_task, run_single_cli_command, send_task_control,
    spawn_task, TaskControlKind, TaskState,
};

#[tauri::command]
pub(crate) async fn inspect_video(
    paths: State<'_, ResolvedRuntimePaths>,
    input_path: String,
) -> Result<VideoInfo, ShellError> {
    run_single_cli_command(
        paths.inner(),
        &[String::from("info"), String::from("--input"), input_path],
        None,
        "video info",
    )
    .await
}

#[tauri::command]
pub(crate) async fn start_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<(), ShellError> {
    spawn_task(app, state.inner(), paths.inner(), request).await
}

#[tauri::command]
pub(crate) async fn check_resume_state(
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<ResumeInspectionResult, ShellError> {
    let (args, stdin_payload) = build_inspect_output_args(&request)?;
    run_single_cli_command(
        paths.inner(),
        &args,
        Some(&stdin_payload),
        "resume inspection",
    )
    .await
}

#[tauri::command]
pub(crate) async fn cancel_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    cancel_running_task(state.inner()).await
}

/// Pause and resume share one command and use the typed control kind to
/// avoid duplicating the permission and dispatch path.
#[tauri::command]
pub(crate) async fn control_task(
    state: State<'_, TaskState>,
    kind: TaskControlKind,
) -> Result<(), ShellError> {
    send_task_control(state.inner(), kind).await
}
