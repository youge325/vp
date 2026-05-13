use serde_json::Value;
use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{TaskRequest, VideoInfo};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{
    build_inspect_output_args, cancel_running_task, pause_running_task, resume_running_task,
    run_single_cli_command, spawn_task, TaskState,
};

#[tauri::command]
pub async fn inspect_video<R: Runtime>(
    app: AppHandle<R>,
    paths: State<'_, ResolvedRuntimePaths>,
    input_path: String,
) -> Result<VideoInfo, ShellError> {
    let raw = run_single_cli_command(
        &app,
        &paths,
        &[String::from("info"), String::from("--input"), input_path],
    )
    .await?;
    serde_json::from_value::<VideoInfo>(raw).map_err(|error| {
        ShellError::SchemaValidation(format!("Unable to deserialize video info: {error}"))
    })
}

#[tauri::command]
pub async fn start_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<(), ShellError> {
    spawn_task(app, state, paths, request).await
}

#[tauri::command]
pub async fn check_resume_state<R: Runtime>(
    app: AppHandle<R>,
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<Value, ShellError> {
    let args = build_inspect_output_args(&request)?;
    run_single_cli_command(&app, &paths, &args).await
}

#[tauri::command]
pub async fn cancel_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    cancel_running_task(state).await
}

#[tauri::command]
pub async fn pause_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    pause_running_task(state).await
}

#[tauri::command]
pub async fn resume_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    resume_running_task(state).await
}
