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
/// Phase 5c — both [`build_process_command`] and the one-shot runner
/// (``tasks::oneshot``) used to inline the exact same four lines for
/// ``Command::new(python).args(["-m","app",sub]).current_dir(...).envs(...)``.
/// Centralising the bootstrap here means a future change to (say) the
/// ``-m app`` module path, the working directory convention, or the
/// environment map only needs to land in one place.
///
/// The returned ``Command`` has only the executable, the subcommand,
/// the working directory and the env map set. Callers are expected to
/// append their own ``--flag value`` arguments, stdio configuration and
/// platform-specific flags (``apply_no_window``, ``spawn_no_window_group``).
pub fn backend_command(paths: &ResolvedRuntimePaths, subcommand: &str) -> Command {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", subcommand]);
    command.current_dir(&paths.backend_dir);
    command.envs(crate::runtime::build_env_map(paths));
    command
}

/// Serialize the four config sections as a single JSON object.
///
/// Phase D.3.1 — the Tauri host now feeds backend config through stdin
/// as ``{decode, workflow, encode, output}`` instead of four separate
/// ``--*-config-json`` command line arguments. The previous wire format
/// risked overflowing the Windows command-line limit (~32 KiB) once the
/// user added more than a couple of preprocess / postprocess filters.
fn build_config_stdin_payload(request: &TaskRequest) -> Result<String, serde_json::Error> {
    serde_json::to_string(&json!({
        "decode": &request.decode_config,
        "workflow": &request.workflow_config,
        "encode": &request.encode_config,
        "output": &request.output_config,
    }))
}

pub fn build_process_command(
    paths: &ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<(Command, String), serde_json::Error> {
    let mut command = backend_command(paths, "process");
    command.args(["--input", &request.input_path]);
    command.arg("--config-stdin");

    if let Some(mode) = request.resume_mode.as_deref() {
        if !mode.is_empty() {
            command.args(["--resume-mode", mode]);
        }
    }

    // stdin is intentionally piped — the caller writes the JSON payload
    // immediately after spawn and then drops the handle to signal EOF.
    command.stdin(Stdio::piped());

    let stdin_payload = build_config_stdin_payload(request)?;
    Ok((command, stdin_payload))
}

pub fn build_inspect_output_args(
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
pub fn apply_no_window(command: &mut Command) {
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
pub fn apply_no_window(_command: &mut Command) {}

#[cfg(windows)]
pub fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.group().creation_flags(CREATE_NO_WINDOW).spawn()
}

#[cfg(not(windows))]
pub fn spawn_no_window_group(command: &mut Command) -> io::Result<AsyncGroupChild> {
    command.group_spawn()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{
        DecodeConfig, DecodeMode, EncodeConfig, FpsMode, InterpolationConfig, OutputConfig,
        PostprocessConfig, PreprocessConfig, ProcessOrder, RateControlConfig, RateControlMode,
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
                    num_frames: 10,
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
                rate_control: RateControlConfig {
                    mode: RateControlMode::Crf,
                    value: json!(18),
                },
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: Some("D:/out".to_string()),
                open_on_complete: true,
                segment_frames: 1000,
            },
            resume_mode: Some("auto".to_string()),
        }
    }

    #[test]
    fn build_inspect_output_args_leads_with_subcommand_input_and_stdin_flag() {
        let request = sample_request();
        let (args, _payload) = build_inspect_output_args(&request).expect("args");
        assert_eq!(args[0], "inspect-output");
        assert_eq!(args[1], "--input");
        assert_eq!(args[2], "D:/in.mp4");
        // Phase D.3.1 — `--config-stdin` replaces the four `--*-config-json`
        // flags as the wire format. Config payload now travels through stdin.
        assert!(
            args.iter().any(|arg| arg == "--config-stdin"),
            "expected --config-stdin flag in {:?}",
            args,
        );
        assert!(
            !args.iter().any(|arg| arg.ends_with("-config-json")),
            "legacy --*-config-json flags should not appear in stdin mode: {:?}",
            args,
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
        // Smoke-check the sibling helper used by ``spawn_task`` —
        // exercises the same packing logic without spawning a process.
        // We can't easily inspect the Command's argv post-construction
        // without running it, so this only validates the stdin payload
        // shape; the command flags are covered by integration tests.
        let request = sample_request();
        let paths = ResolvedRuntimePaths {
            backend_dir: std::path::PathBuf::from("."),
            runtime_root: None,
            python_executable: std::path::PathBuf::from("python"),
            ffmpeg_path: None,
            ffprobe_path: None,
            model_dir: None,
            tensorrt_dir: None,
            output_dir: std::path::PathBuf::from("."),
            log_dir: std::path::PathBuf::from("."),
        };
        let (_command, payload) = build_process_command(&paths, &request).expect("command");
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
