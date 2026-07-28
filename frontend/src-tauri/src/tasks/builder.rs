use std::io;
use std::process::Stdio;

use command_group::{AsyncCommandGroup, AsyncGroupChild};
use serde_json::json;
use tokio::process::Command;

use crate::models::TaskRequest;
use crate::runtime::ResolvedRuntimePaths;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;

/// Single source of truth for spawning the Python backend.
///
/// Long-running and one-shot commands share this bootstrap so the module,
/// working-directory and environment conventions cannot drift.
///
/// The returned ``Command`` has only the executable, the subcommand,
/// the working directory and the env map set. Callers are expected to
/// append their own ``--flag value`` arguments, stdio configuration and
/// platform-specific flags (``apply_no_window``, ``spawn_no_window_group``).
pub(crate) fn backend_command(paths: &ResolvedRuntimePaths, subcommand: &str) -> Command {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", subcommand]);
    command.current_dir(&paths.backend_dir);
    command.envs(crate::runtime::build_env_map(paths));
    command
}

/// Serialize the four config sections as a single JSON object.
///
/// The Tauri host feeds backend config through stdin
/// as ``{decode, workflow, encode, output}``, keeping the process command
/// short even when a workflow contains many filters.
fn build_config_stdin_payload(request: &TaskRequest) -> Result<String, serde_json::Error> {
    serde_json::to_string(&json!({
        "decode": &request.decode_config,
        "workflow": &request.workflow_config,
        "encode": &request.encode_config,
        "output": &request.output_config,
    }))
}

pub(crate) fn build_process_command(
    paths: &ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<(Command, String), serde_json::Error> {
    let mut command = backend_command(paths, "process");
    command.args(["--input", &request.input_path]);
    command.arg("--config-stdin");

    if let Some(mode) = request.resume_mode.as_ref() {
        let serialized_mode = serde_json::to_value(mode)?;
        let mode = serialized_mode
            .as_str()
            .expect("ResumeMode must serialize as a string");
        command.args(["--resume-mode", mode]);
    }

    // stdin is intentionally piped — the caller writes the JSON payload
    // immediately after spawn and then drops the handle to signal EOF.
    command.stdin(Stdio::piped());

    let stdin_payload = build_config_stdin_payload(request)?;
    Ok((command, stdin_payload))
}

pub(crate) fn build_inspect_output_args(
    request: &TaskRequest,
) -> Result<(Vec<String>, String), serde_json::Error> {
    let args = vec![
        String::from("inspect-output"),
        String::from("--input"),
        request.input_path.clone(),
        String::from("--config-stdin"),
    ];
    let stdin_payload = build_config_stdin_payload(request)?;
    Ok((args, stdin_payload))
}

#[cfg(windows)]
pub(crate) fn apply_no_window(command: &mut Command) {
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
pub(crate) fn apply_no_window(_command: &mut Command) {}

#[cfg(windows)]
pub(crate) fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.kill_on_drop(true);
    command
        .group()
        .kill_on_drop(true)
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
}

#[cfg(not(windows))]
pub(crate) fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.kill_on_drop(true);
    command.group().kill_on_drop(true).spawn()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::config::{
        DecodeConfig, DecodeMode, EncodeConfig, FpsMode, InterpolationConfig, OutputConfig,
        PostprocessConfig, PreprocessConfig, ProcessOrder, RateControlConfig,
        SuperResolutionConfig, TensorBackend, WorkflowConfig,
    };
    use serde_json::json;

    fn sample_request() -> TaskRequest {
        TaskRequest {
            input_path: "D:/in.mp4".to_string(),
            decode_config: DecodeConfig {
                mode: DecodeMode::Software,
                hwaccel: None,
                hwaccel_device: None,
                decoder: Some("software".to_string()),
                options: Default::default(),
            },
            workflow_config: WorkflowConfig {
                fps_mode: FpsMode::Multi,
                process_order: ProcessOrder::SuperResolutionThenInterpolation,
                interpolation: InterpolationConfig {
                    enabled: true,
                    target_fps: 60.0,
                    multi: 2,
                    algorithm: "rife".to_string(),
                    model: "4.25".to_string(),
                    onnx_model: None,
                    scale: 1.0,
                    fp16: false,
                    tensor_backend: TensorBackend::Pytorch,
                    engine: "cuda".to_string(),
                },
                super_resolution: SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                    onnx_model: None,
                    tensor_backend: TensorBackend::Onnx,
                    engine: "cuda".to_string(),
                    num_frames: 10.try_into().expect("positive frame window"),
                },
                preprocess: PreprocessConfig {
                    enabled: false,
                    filters: Vec::new(),
                },
                postprocess: PostprocessConfig {
                    enabled: false,
                    filters: Vec::new(),
                },
            },
            encode_config: EncodeConfig {
                codec: "libx264".to_string(),
                family: "cpu".to_string(),
                container: "mp4".to_string(),
                keep_audio: true,
                rate_control: serde_json::from_value::<RateControlConfig>(json!({
                    "mode": "crf",
                    "value": 18
                }))
                .expect("rate control contract"),
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: Some("D:/out".to_string()),
                open_on_complete: true,
                segment_frames: 1000.try_into().expect("positive segment size"),
            },
            resume_mode: Some(crate::models::task::ResumeMode::Auto),
        }
    }

    #[test]
    fn build_inspect_output_args_leads_with_subcommand_input_and_stdin_flag() {
        let request = sample_request();
        let (args, _payload) = build_inspect_output_args(&request).expect("args");
        assert_eq!(args[0], "inspect-output");
        assert_eq!(args[1], "--input");
        assert_eq!(args[2], "D:/in.mp4");
        assert_eq!(
            args,
            ["inspect-output", "--input", "D:/in.mp4", "--config-stdin"],
        );
    }

    #[test]
    fn build_inspect_output_stdin_payload_packs_all_four_sections() {
        let request = sample_request();
        let (_args, payload) = build_inspect_output_args(&request).expect("args");
        let parsed = serde_json::from_str::<serde_json::Value>(&payload)
            .expect("stdin payload must be valid JSON");
        let obj = parsed.as_object().expect("payload root must be object");
        for key in ["decode", "workflow", "encode", "output"] {
            assert!(
                obj.contains_key(key),
                "stdin payload missing `{key}` section: {payload}",
            );
        }
    }

    #[test]
    fn build_inspect_output_stdin_payload_serializes_camel_case_fields() {
        let request = sample_request();
        let (_args, payload) = build_inspect_output_args(&request).expect("args");
        // Rust uses snake_case fields (fps_mode) but serializes to camelCase (fpsMode).
        assert!(
            payload.contains("\"fpsMode\""),
            "expected camelCase fpsMode in {payload}",
        );
        assert!(
            payload.contains("\"processOrder\""),
            "expected camelCase processOrder in {payload}",
        );
        assert!(
            !payload.contains("\"fps_mode\""),
            "snake_case must not leak into wire payload: {payload}",
        );
    }

    #[test]
    fn build_process_command_returns_stdin_payload_with_all_sections() {
        // Smoke-check the sibling helper used by ``spawn_task`` without
        // spawning a process.
        let request = sample_request();
        let paths = ResolvedRuntimePaths {
            app_data_dir: std::path::PathBuf::from("."),
            backend_dir: std::path::PathBuf::from("."),
            runtime_root: None,
            python_executable: std::path::PathBuf::from("python"),
            ffmpeg_path: None,
            ffprobe_path: None,
            model_dir: None,
            rife_model_version: "4.25".to_string(),
            tensorrt_dir: None,
            log_dir: std::path::PathBuf::from("."),
        };
        let (command, payload) = build_process_command(&paths, &request).expect("command");
        let args = command
            .as_std()
            .get_args()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--resume-mode", "auto"]));
        let parsed = serde_json::from_str::<serde_json::Value>(&payload)
            .expect("stdin payload must be valid JSON");
        let obj = parsed.as_object().expect("payload root must be object");
        for key in ["decode", "workflow", "encode", "output"] {
            assert!(
                obj.contains_key(key),
                "process stdin payload missing `{key}` section: {payload}",
            );
        }
    }
}
