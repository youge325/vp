use std::io;
use std::process::Stdio;

use command_group::{AsyncCommandGroup, AsyncGroupChild};
use tokio::process::Command;

use crate::models::TaskRequest;
use crate::runtime::ResolvedRuntimePaths;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;

pub fn build_process_command(
    paths: &ResolvedRuntimePaths,
    request: &TaskRequest,
) -> Result<Command, serde_json::Error> {
    let mut command = Command::new(&paths.python_executable);
    command.args(["-m", "app", "process"]);
    command.args(["--input", &request.input_path]);

    let decode_json = serde_json::to_string(&request.decode_config)?;
    let workflow_json = serde_json::to_string(&request.workflow_config)?;
    let encode_json = serde_json::to_string(&request.encode_config)?;
    let output_json = serde_json::to_string(&request.output_config)?;

    command.args(["--decode-config-json", &decode_json]);
    command.args(["--workflow-config-json", &workflow_json]);
    command.args(["--encode-config-json", &encode_json]);
    command.args(["--output-config-json", &output_json]);

    if let Some(mode) = request.resume_mode.as_deref() {
        if !mode.is_empty() {
            command.args(["--resume-mode", mode]);
        }
    }

    command.current_dir(&paths.backend_dir);
    command.envs(crate::runtime::build_env_map(paths));
    command.stdin(Stdio::null());
    Ok(command)
}

pub fn build_inspect_output_args(request: &TaskRequest) -> Result<Vec<String>, serde_json::Error> {
    let mut args = vec![
        String::from("inspect-output"),
        String::from("--input"),
        request.input_path.clone(),
    ];

    args.push(String::from("--decode-config-json"));
    args.push(serde_json::to_string(&request.decode_config)?);
    args.push(String::from("--workflow-config-json"));
    args.push(serde_json::to_string(&request.workflow_config)?);
    args.push(String::from("--encode-config-json"));
    args.push(serde_json::to_string(&request.encode_config)?);
    args.push(String::from("--output-config-json"));
    args.push(serde_json::to_string(&request.output_config)?);

    Ok(args)
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
        AnimeConfig, DecodeConfig, EncodeConfig, InterpolationConfig, OutputConfig,
        PostprocessConfig, PreprocessConfig, RateControlConfig, SuperResolutionConfig,
        WorkflowConfig,
    };
    use serde_json::json;

    fn sample_request() -> TaskRequest {
        TaskRequest {
            input_path: "D:/in.mp4".to_string(),
            decode_config: DecodeConfig {
                mode: "software".to_string(),
                hwaccel: None,
                hwaccel_device: None,
                decoder: Some("software".to_string()),
                options: Default::default(),
            },
            workflow_config: WorkflowConfig {
                fps_mode: "multi".to_string(),
                process_order: "super_resolution_then_interpolation".to_string(),
                interpolation: InterpolationConfig {
                    enabled: true,
                    target_fps: 60.0,
                    multi: 2,
                    algorithm: "rife".to_string(),
                    model: "4.25".to_string(),
                    onnx_model: None,
                    scale: 1.0,
                    fp16: false,
                    tensor_backend: "pytorch".to_string(),
                    engine: "cuda".to_string(),
                },
                super_resolution: SuperResolutionConfig {
                    enabled: false,
                    scale_factor: 2.0,
                    algorithm: "placeholder".to_string(),
                    onnx_model: None,
                },
                anime: AnimeConfig {
                    enabled: false,
                    profile: "clean-lines".to_string(),
                    denoise: 10,
                    edge_boost: 15,
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
                    mode: "crf".to_string(),
                    value: json!(18),
                },
                options: Default::default(),
            },
            output_config: OutputConfig {
                output_dir: "D:/out".to_string(),
                open_on_complete: true,
                segment_frames: 1000,
            },
            resume_mode: Some("auto".to_string()),
        }
    }

    #[test]
    fn build_inspect_output_args_leads_with_subcommand_and_input() {
        let request = sample_request();
        let args = build_inspect_output_args(&request).expect("args");
        assert_eq!(args[0], "inspect-output");
        assert_eq!(args[1], "--input");
        assert_eq!(args[2], "D:/in.mp4");
    }

    #[test]
    fn build_inspect_output_args_includes_all_four_config_payloads() {
        let request = sample_request();
        let args = build_inspect_output_args(&request).expect("args");

        let flags: Vec<&String> = args
            .iter()
            .filter(|arg| arg.starts_with("--") && arg.ends_with("-config-json"))
            .collect();
        assert_eq!(flags.len(), 4, "expected exactly 4 config-json flags, got {:?}", flags);

        // Each flag should be followed by a valid JSON string.
        for (index, arg) in args.iter().enumerate() {
            if arg.starts_with("--") && arg.ends_with("-config-json") {
                let payload = &args[index + 1];
                serde_json::from_str::<serde_json::Value>(payload)
                    .unwrap_or_else(|err| panic!("invalid JSON for {arg}: {err} -> {payload}"));
            }
        }
    }

    #[test]
    fn build_inspect_output_args_serializes_camel_case_fields() {
        let request = sample_request();
        let args = build_inspect_output_args(&request).expect("args");

        let workflow_json = args
            .iter()
            .position(|arg| arg == "--workflow-config-json")
            .map(|idx| &args[idx + 1])
            .expect("workflow json present");

        // Rust uses snake_case fields (fps_mode) but serializes to camelCase (fpsMode).
        assert!(workflow_json.contains("fpsMode"), "expected camelCase fpsMode in {workflow_json}");
        assert!(workflow_json.contains("processOrder"), "expected camelCase processOrder");
        assert!(!workflow_json.contains("fps_mode"), "snake_case must not leak");
    }
}
