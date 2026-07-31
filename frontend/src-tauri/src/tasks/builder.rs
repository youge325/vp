use std::process::Stdio;

use tokio::process::Command;

use crate::generated::{
    BackendCommandSpec, BackendProcessSpec, CheckResumeStateInvocation, StartTaskInvocation,
    StartTaskSpec,
};
use crate::models::{RuntimeConfigBundle, TaskRequest};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::subprocess::{ProcessGroupChild, ProcessGroupSpawnError};

/// Single source of truth for spawning the Python backend.
///
/// Long-running and one-shot commands share this bootstrap so the module,
/// working-directory and environment conventions cannot drift.
///
/// CLI arguments are emitted only by the manifest-generated sealed spec;
/// callers configure stdio and spawn policy but cannot append an arbitrary
/// backend protocol surface through this adapter.
pub(super) fn backend_command<S: BackendCommandSpec>(
    paths: &ResolvedRuntimePaths,
    invocation: &S::Invocation,
) -> Command {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", S::SUBCOMMAND]);
    command.args(S::arguments(invocation));
    command.current_dir(&paths.backend_dir);
    command.envs(crate::runtime::build_env_map(paths));
    command
}

/// Serialize the four config sections as a single JSON object.
///
/// The Tauri host feeds backend config through stdin
/// as ``{decode, workflow, encode, output}``, keeping the process command
/// short even when a workflow contains many filters.
fn build_runtime_config_bundle(request: &TaskRequest) -> RuntimeConfigBundle {
    RuntimeConfigBundle {
        decode: request.decode_config.clone(),
        workflow: request.workflow_config.clone(),
        encode: request.encode_config.clone(),
        output: request.output_config.clone(),
    }
}

fn build_start_task_invocation(request: &TaskRequest) -> StartTaskInvocation {
    StartTaskInvocation {
        input_path: request.input_path.clone(),
        resume_mode: request.resume_mode,
        config: build_runtime_config_bundle(request),
    }
}

pub(super) fn build_process_command(
    paths: &ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<(Command, String), serde_json::Error> {
    let invocation = build_start_task_invocation(request);
    let mut command = backend_command::<StartTaskSpec>(paths, &invocation);

    // stdin is intentionally piped — the caller writes the JSON payload
    // immediately after spawn and then drops the handle to signal EOF.
    command.stdin(Stdio::piped());

    let stdin_payload = serde_json::to_string(StartTaskSpec::stdin_payload(&invocation))?;
    Ok((command, stdin_payload))
}

pub(super) fn build_resume_inspection_invocation(
    request: &TaskRequest,
) -> CheckResumeStateInvocation {
    CheckResumeStateInvocation {
        input_path: request.input_path.clone(),
        config: build_runtime_config_bundle(request),
    }
}

pub(super) fn spawn_no_window_group(
    command: &mut Command,
) -> Result<ProcessGroupChild, ProcessGroupSpawnError> {
    ProcessGroupChild::spawn(command)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::config::{
        DecodeConfig, DecodeMode, EncodeConfig, FpsMode, InferenceEngine, InterpolationConfig,
        OutputConfig, PostprocessConfig, PreprocessConfig, ProcessOrder, RateControlConfig,
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
                    engine: InferenceEngine::Cuda,
                },
                super_resolution: SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                    onnx_model: None,
                    tensor_backend: TensorBackend::Onnx,
                    engine: InferenceEngine::Cuda,
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
                output_dir: Some(
                    "D:/out"
                        .to_string()
                        .try_into()
                        .expect("valid output directory"),
                ),
                open_on_complete: true,
                segment_frames: 1000.try_into().expect("positive segment size"),
            },
            resume_mode: Some(crate::models::task::ResumeMode::Auto),
        }
    }

    #[test]
    fn resume_inspection_args_only_contain_command_specific_flags() {
        let request = sample_request();
        let invocation = build_resume_inspection_invocation(&request);
        let args = crate::generated::CheckResumeStateSpec::arguments(&invocation);
        assert_eq!(args, ["--input", "D:/in.mp4", "--config-stdin"]);
    }

    #[test]
    fn build_inspect_output_stdin_payload_packs_all_four_sections() {
        let request = sample_request();
        let invocation = build_resume_inspection_invocation(&request);
        let parsed =
            serde_json::to_value(&invocation.config).expect("stdin payload must be valid JSON");
        let obj = parsed.as_object().expect("payload root must be object");
        for key in ["decode", "workflow", "encode", "output"] {
            assert!(
                obj.contains_key(key),
                "stdin payload missing `{key}` section: {parsed}",
            );
        }
    }

    #[test]
    fn build_inspect_output_stdin_payload_serializes_camel_case_fields() {
        let request = sample_request();
        let invocation = build_resume_inspection_invocation(&request);
        let payload = serde_json::to_string(&invocation.config).expect("serialize bundle");
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

    #[test]
    fn generated_process_spec_maps_every_resume_mode_without_json_roundtrip() {
        let cases = [
            (crate::models::task::ResumeMode::Auto, "auto"),
            (crate::models::task::ResumeMode::ForceFresh, "force-fresh"),
            (crate::models::task::ResumeMode::ForceResume, "force-resume"),
        ];
        for (mode, expected) in cases {
            let mut request = sample_request();
            request.resume_mode = Some(mode);
            let invocation = build_start_task_invocation(&request);
            let arguments = StartTaskSpec::arguments(&invocation);
            let resume_index = arguments
                .iter()
                .position(|argument| argument == "--resume-mode")
                .expect("generated resume flag");
            assert_eq!(arguments[resume_index + 1], expected);
        }
    }
}
