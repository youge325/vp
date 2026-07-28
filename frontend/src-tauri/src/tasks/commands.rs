use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{ResumeInspectionResult, TaskRequest, VideoInfo};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{
    build_inspect_output_args, run_single_cli_command, send_task_control, spawn_task,
    TaskApplicationError, TaskControlKind, TaskState, TaskStateError,
};

fn map_task_application_error(error: TaskApplicationError) -> ShellError {
    match error {
        TaskApplicationError::Shell(error) => error,
        TaskApplicationError::State(error) => match error {
            TaskStateError::AlreadyRunning => {
                ShellError::InvalidInput("A task is already running.".to_string())
            }
            TaskStateError::StartLeaseExpired => {
                ShellError::InvalidInput("The task start lease is no longer active.".to_string())
            }
            TaskStateError::NoActiveTask => ShellError::NoActiveTask,
            TaskStateError::StillStarting => {
                ShellError::InvalidInput("The task is still starting.".to_string())
            }
            TaskStateError::AlreadyCancelling => {
                ShellError::InvalidInput("The task is already being cancelled.".to_string())
            }
            TaskStateError::AlreadyFinishing => {
                ShellError::InvalidInput("The task is already finishing.".to_string())
            }
        },
    }
}

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
    spawn_task(app, state.inner(), paths.inner(), request)
        .await
        .map_err(map_task_application_error)
}

#[tauri::command]
pub(crate) async fn check_resume_state(
    paths: State<'_, ResolvedRuntimePaths>,
    request: TaskRequest,
) -> Result<ResumeInspectionResult, ShellError> {
    let (args, stdin_payload) = build_inspect_output_args(&request).map_err(|error| {
        ShellError::SchemaValidation(format!(
            "Unable to encode resume inspection configuration: {error}"
        ))
    })?;
    run_single_cli_command(
        paths.inner(),
        &args,
        Some(&stdin_payload),
        "resume inspection",
    )
    .await
}

/// Pause, resume and cancel share one typed command surface.
#[tauri::command]
pub(crate) async fn control_task(
    state: State<'_, TaskState>,
    kind: TaskControlKind,
) -> Result<(), ShellError> {
    send_task_control(state.inner(), kind)
        .await
        .map_err(map_task_application_error)
}

#[cfg(test)]
mod tests {
    use super::map_task_application_error;
    use crate::error::ShellError;
    use crate::tasks::{TaskApplicationError, TaskStateError};

    #[test]
    fn command_adapter_maps_task_state_errors_to_the_shell_contract() {
        let cases = [
            (
                TaskStateError::AlreadyRunning,
                "invalid input: A task is already running.",
            ),
            (
                TaskStateError::StartLeaseExpired,
                "invalid input: The task start lease is no longer active.",
            ),
            (TaskStateError::NoActiveTask, "no running task"),
            (
                TaskStateError::StillStarting,
                "invalid input: The task is still starting.",
            ),
            (
                TaskStateError::AlreadyCancelling,
                "invalid input: The task is already being cancelled.",
            ),
            (
                TaskStateError::AlreadyFinishing,
                "invalid input: The task is already finishing.",
            ),
        ];

        for (domain_error, expected_message) in cases {
            let shell_error = map_task_application_error(TaskApplicationError::State(domain_error));
            assert_eq!(shell_error.to_string(), expected_message);
            if matches!(domain_error, TaskStateError::NoActiveTask) {
                assert!(matches!(shell_error, ShellError::NoActiveTask));
            } else {
                assert!(matches!(shell_error, ShellError::InvalidInput(_)));
            }
        }
    }

    #[test]
    fn command_adapter_preserves_existing_shell_errors() {
        let shell_error = map_task_application_error(TaskApplicationError::Shell(
            ShellError::ControllerUnavailable,
        ));
        assert!(matches!(shell_error, ShellError::ControllerUnavailable));
    }
}
