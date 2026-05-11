use serde_json::Value;
use tauri::{AppHandle, Runtime, State};

use crate::models::{TaskRequest, VideoInfo};
use crate::tasks::{
    build_inspect_output_args, cancel_running_task, pause_running_task,
    resume_running_task, run_single_cli_command, spawn_task, TaskState,
};

#[tauri::command]
pub async fn inspect_video<R: Runtime>(
    app: AppHandle<R>,
    input_path: String,
) -> Result<VideoInfo, String> {
    let raw = run_single_cli_command(
        &app,
        &[String::from("info"), String::from("--input"), input_path],
    )
    .await?;
    serde_json::from_value::<VideoInfo>(raw)
        .map_err(|error| format!("Unable to deserialize video info: {error}"))
}

#[tauri::command]
pub async fn start_task<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, TaskState>,
    request: TaskRequest,
) -> Result<(), String> {
    spawn_task(app, state, request).await
}

#[tauri::command]
pub async fn check_resume_state<R: Runtime>(
    app: AppHandle<R>,
    request: TaskRequest,
) -> Result<Value, String> {
    let args = build_inspect_output_args(&request)
        .map_err(|error| format!("Unable to build resume inspection args: {error}"))?;
    run_single_cli_command(&app, &args).await
}

#[tauri::command]
pub async fn cancel_task(state: State<'_, TaskState>) -> Result<(), String> {
    cancel_running_task(state).await
}

#[tauri::command]
pub async fn pause_task(state: State<'_, TaskState>) -> Result<(), String> {
    pause_running_task(state).await
}

#[tauri::command]
pub async fn resume_task(state: State<'_, TaskState>) -> Result<(), String> {
    resume_running_task(state).await
}
