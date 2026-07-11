use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{ResumeInspectionResult, TaskRequest, VideoInfo};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{
    build_inspect_output_args, cancel_running_task, run_single_cli_command, send_task_control,
    spawn_task, TaskControlKind, TaskState,
};

#[tauri::command]
pub async fn inspect_video(
    paths: State<'_, ResolvedRuntimePaths>,
    input_path: String,
) -> Result<VideoInfo, ShellError> {
    let outcome = run_single_cli_command(
        paths.inner(),
        &[String::from("info"), String::from("--input"), input_path],
        None,
    )
    .await?;
    let value = outcome.into_result()?;
    serde_json::from_value::<VideoInfo>(value).map_err(|error| {
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
    spawn_task(app, state.inner(), paths.inner(), request).await
}

#[tauri::command]
pub async fn check_resume_state(
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<ResumeInspectionResult, ShellError> {
    let (args, stdin_payload) = build_inspect_output_args(&request)?;
    let outcome = run_single_cli_command(paths.inner(), &args, Some(&stdin_payload)).await?;
    let value = outcome.into_result()?;
    serde_json::from_value::<ResumeInspectionResult>(value).map_err(|error| {
        ShellError::SchemaValidation(format!("Unable to deserialize resume inspection: {error}"))
    })
}

#[tauri::command]
pub async fn cancel_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    cancel_running_task(state.inner()).await
}

/// Phase A — pause / resume 合并为单一 ``control_task``。前端传 ``kind``
/// 区分意图,Rust 端拿 ``TaskControlKind`` 枚举去 dispatch,避免两条几乎
/// 一样的 ``#[tauri::command]`` 走重复 ACL/permission 链路。
#[tauri::command]
pub async fn control_task(
    state: State<'_, TaskState>,
    kind: TaskControlKind,
) -> Result<(), ShellError> {
    send_task_control(state.inner(), kind).await
}
