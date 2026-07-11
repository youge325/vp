use schemars::schema_for;
use std::fs;
use std::path::Path;

fn main() {
    let schemas_dir = Path::new("schemas");
    fs::create_dir_all(schemas_dir).expect("failed to create schemas/ directory");

    macro_rules! dump {
        ($ty:ty, $name:literal) => {{
            let schema = schema_for!($ty);
            let json = serde_json::to_string_pretty(&schema).unwrap();
            let path = schemas_dir.join(format!("{}.schema.json", $name));
            fs::write(&path, &json).expect("failed to write schema file");
            println!("wrote {}", path.display());
        }};
    }

    use vp_workbench_lib::models::*;

    dump!(DecodeConfig, "decode_config");
    dump!(EncodeConfig, "encode_config");
    dump!(OutputConfig, "output_config");
    dump!(InterpolationConfig, "interpolation_config");
    dump!(SuperResolutionConfig, "super_resolution_config");
    dump!(PreprocessConfig, "preprocess_config");
    dump!(PostprocessConfig, "postprocess_config");
    dump!(FilterStep, "filter_step");
    dump!(WorkflowConfig, "workflow_config");
    dump!(RateControlConfig, "rate_control_config");
    dump!(WorkbenchPreset, "workbench_preset");
    dump!(TaskRequest, "task_request");
    dump!(TaskProgressPayload, "task_progress_payload");
    dump!(TaskCompletedPayload, "task_completed_payload");
    dump!(TaskErrorPayload, "task_error_payload");
    dump!(TaskLogPayload, "task_log_payload");
    dump!(ResumeStatusPayload, "resume_status_payload");
}
