use serde_json::Value;
use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{TaskRequest, VideoInfo};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{
    build_inspect_output_args, cancel_running_task, pause_running_task, resume_running_task,
    run_single_cli_command, spawn_task, CliOutcome, TaskState,
};

/// Phase 5c — map the typed [`CliOutcome`] returned by the one-shot
/// runner into the legacy ``Result<Value, ShellError>`` shape that
/// downstream callers expect.
///
/// - ``Ok(value)`` → forward verbatim.
/// - ``FailedWithEnvelope`` → fold the envelope's ``code`` and
///   ``message`` into a ``ShellError::BackendExit`` so the frontend
///   sees the structured failure via the invoke error channel.
/// - ``FailedWithoutEnvelope`` → forward the stderr summary as a
///   ``BackendExit`` error.
fn cli_outcome_into_value(outcome: CliOutcome) -> Result<Value, ShellError> {
    match outcome {
        CliOutcome::Ok(value) => Ok(value),
        CliOutcome::FailedWithEnvelope(envelope) => {
            // ``serde_plain::to_string`` would let us emit just the
            // snake_case code without dragging in another dep; format
            // the Debug repr instead — the code is enum-typed so the
            // output is stable enough for log surfaces while keeping
            // the human-readable message intact for the user.
            Err(ShellError::BackendExit(format!(
                "{} ({:?})",
                envelope.message, envelope.code
            )))
        }
        CliOutcome::FailedWithoutEnvelope(message) => Err(ShellError::BackendExit(message)),
    }
}

#[tauri::command]
pub async fn inspect_video<R: Runtime>(
    app: AppHandle<R>,
    paths: State<'_, ResolvedRuntimePaths>,
    input_path: String,
) -> Result<VideoInfo, ShellError> {
    let outcome = run_single_cli_command(
        &app,
        paths.inner(),
        &[String::from("info"), String::from("--input"), input_path],
        None,
    )
    .await?;
    let value = cli_outcome_into_value(outcome)?;
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
pub async fn check_resume_state<R: Runtime>(
    app: AppHandle<R>,
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<Value, ShellError> {
    let (args, stdin_payload) = build_inspect_output_args(&request)?;
    let outcome = run_single_cli_command(&app, paths.inner(), &args, Some(&stdin_payload)).await?;
    cli_outcome_into_value(outcome)
}

#[tauri::command]
pub async fn cancel_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    cancel_running_task(state.inner()).await
}

#[tauri::command]
pub async fn pause_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    pause_running_task(state.inner()).await
}

#[tauri::command]
pub async fn resume_task(state: State<'_, TaskState>) -> Result<(), ShellError> {
    resume_running_task(state.inner()).await
}
