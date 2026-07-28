use serde_json::{json, Value};

use super::boundary::{
    BackendTaskErrorPayload, EnvironmentCacheEntry, EnvironmentCheckPayload,
    EnvironmentCheckResult, ResumeInspectionResult, ResumeMode, TaskErrorPayload,
    TaskProgressPayload, TaskRequest, VideoInfo, WorkbenchPreset, WorkbenchPresetEntry,
    WorkflowConfig,
};

fn valid_preset_value() -> Value {
    json!({
        "decodeConfig": {
            "mode": "software",
            "hwaccel": null,
            "hwaccelDevice": null,
            "decoder": null,
            "options": {}
        },
        "workflowConfig": {
            "fpsMode": "multi",
            "processOrder": "super_resolution_then_interpolation",
            "interpolation": {
                "enabled": false,
                "targetFps": 60.0,
                "multi": 2,
                "algorithm": "rife",
                "model": "4.25",
                "onnxModel": null,
                "scale": 1.0,
                "fp16": false,
                "tensorBackend": "pytorch",
                "engine": "cuda"
            },
            "superResolution": {
                "enabled": false,
                "scaleFactor": 2.0,
                "algorithm": "onnx",
                "onnxModel": null,
                "tensorBackend": "onnx",
                "engine": "cuda",
                "numFrames": 10
            },
            "preprocess": { "enabled": false, "filters": [] },
            "postprocess": { "enabled": false, "filters": [] }
        },
        "encodeConfig": {
            "codec": "libx264",
            "family": "software",
            "container": "mp4",
            "keepAudio": true,
            "rateControl": { "mode": "crf", "value": 18 },
            "options": {}
        },
        "outputConfig": {
            "outputDir": "D:/out",
            "openOnComplete": false,
            "segmentFrames": 120
        }
    })
}

fn minimal_environment_result() -> Value {
    json!({
        "ffmpeg": {
            "available": true,
            "hwaccels": [],
            "encoderProfiles": [],
            "decoderProfiles": []
        },
        "gpu": { "adapters": [] },
        "tensorEngines": {
            "pytorch": [],
            "paddle": [],
            "onnx": []
        },
        "interpolationAlgorithms": [],
        "superResolutionAlgorithms": [],
        "runtimeMode": "bundled"
    })
}

#[test]
fn preset_round_trip_preserves_canonical_field_names() {
    let raw = valid_preset_value();
    let preset: WorkbenchPreset = serde_json::from_value(raw.clone()).expect("valid preset");
    let serialized = serde_json::to_value(preset).expect("serialize preset");

    assert_eq!(serialized, raw);
}

#[test]
fn output_config_rejects_zero_segment_frames() {
    let mut raw = valid_preset_value();
    raw["outputConfig"]["segmentFrames"] = json!(0);

    assert!(serde_json::from_value::<WorkbenchPreset>(raw).is_err());
}

#[test]
fn workflow_requires_explicit_canonical_fields() {
    let raw = json!({
        "fpsMode": "multi",
        "processOrder": "super_resolution_then_interpolation",
        "interpolation": {
            "enabled": false,
            "targetFps": 60.0,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": false,
            "tensorBackend": "pytorch"
        },
        "superResolution": {
            "enabled": false,
            "scaleFactor": 2.0,
            "algorithm": "onnx"
        }
    });

    let error = serde_json::from_value::<WorkflowConfig>(raw)
        .expect_err("generated boundary requires every non-optional field");
    assert!(error.to_string().contains("algorithm"));
}

#[test]
fn filter_step_preserves_free_form_values() {
    let mut raw = valid_preset_value()["workflowConfig"].clone();
    raw["preprocess"] = json!({
        "enabled": true,
        "filters": [
            { "kind": "scale", "enabled": true, "params": {} },
            {
                "kind": "color",
                "enabled": true,
                "params": { "gamma": 1.2, "nested": { "mode": "linear" } }
            }
        ]
    });

    let workflow: WorkflowConfig = serde_json::from_value(raw).expect("workflow filters");
    let serialized = serde_json::to_value(workflow).expect("serialize workflow filters");

    assert_eq!(serialized["preprocess"]["filters"][0]["params"], json!({}));
    assert_eq!(
        serialized["preprocess"]["filters"][1]["params"],
        json!({ "gamma": 1.2, "nested": { "mode": "linear" } })
    );
}

#[test]
fn workflow_rejects_unknown_fields() {
    let mut value = valid_preset_value()["workflowConfig"].clone();
    value["unexpected"] = json!(true);

    let error = serde_json::from_value::<WorkflowConfig>(value)
        .expect_err("unknown workflow fields must be rejected");
    assert!(error.to_string().contains("unexpected"));
}

#[test]
fn preset_rejects_unknown_fields() {
    let mut value = valid_preset_value();
    value["unexpected"] = json!(1);
    let error = serde_json::from_value::<WorkbenchPreset>(value)
        .expect_err("unknown preset fields must be rejected");
    assert!(error.to_string().contains("unexpected"));
}

#[test]
fn task_request_defaults_resume_mode_and_round_trips_camel_case() {
    let preset = valid_preset_value();
    let raw = json!({
        "inputPath": "D:/input.mp4",
        "decodeConfig": preset["decodeConfig"],
        "workflowConfig": preset["workflowConfig"],
        "encodeConfig": preset["encodeConfig"],
        "outputConfig": preset["outputConfig"]
    });

    let request: TaskRequest = serde_json::from_value(raw).expect("request without resume mode");
    let serialized = serde_json::to_value(request).expect("serialize task request");

    assert_eq!(serialized["inputPath"], json!("D:/input.mp4"));
    assert_eq!(serialized["resumeMode"], Value::Null);
    assert!(serialized.get("input_path").is_none());
}

#[test]
fn task_request_rejects_unknown_fields() {
    let preset = valid_preset_value();
    let mut value = json!({
        "inputPath": "D:/input.mp4",
        "decodeConfig": preset["decodeConfig"],
        "workflowConfig": preset["workflowConfig"],
        "encodeConfig": preset["encodeConfig"],
        "outputConfig": preset["outputConfig"],
        "resumeMode": "auto"
    });
    value["unexpected"] = json!(true);
    let error = serde_json::from_value::<TaskRequest>(value)
        .expect_err("unknown task fields must be rejected");
    assert!(error.to_string().contains("unexpected"));
}

#[test]
fn resume_mode_uses_cli_wire_values() {
    assert_eq!(
        serde_json::to_value(ResumeMode::ForceFresh).expect("serialize resume mode"),
        json!("force-fresh")
    );
    assert_eq!(
        serde_json::from_value::<ResumeMode>(json!("force-resume"))
            .expect("deserialize resume mode"),
        ResumeMode::ForceResume
    );
    assert!(serde_json::from_value::<ResumeMode>(json!("invalid")).is_err());
}

#[test]
fn video_info_uses_camel_case_and_enforces_unsigned_dimensions() {
    let raw = json!({
        "fps": 24.0,
        "width": 1920,
        "height": 1080,
        "videoCodec": "h264"
    });
    let info: VideoInfo = serde_json::from_value(raw.clone()).expect("video info");
    assert_eq!(
        serde_json::to_value(info).expect("serialize video info"),
        raw
    );

    let mut invalid = raw;
    invalid["width"] = json!(-1);
    assert!(serde_json::from_value::<VideoInfo>(invalid).is_err());
}

#[test]
fn video_info_rejects_unclassified_envelope_fields() {
    let raw = json!({
        "type": "info",
        "fps": 24.0,
        "width": 1920,
        "height": 1080,
        "videoCodec": "h264"
    });
    let error =
        serde_json::from_value::<VideoInfo>(raw).expect_err("envelope must be classified first");
    assert!(error.to_string().contains("type"));
}

#[test]
fn resume_inspection_round_trip_preserves_mixed_backend_aliases() {
    let raw = json!({
        "type": "resume_inspection",
        "pipeline_kind": "streaming",
        "outputPath": "D:/out.mp4",
        "input_path": "D:/in.mp4",
        "finalExists": true,
        "sidecarExists": true,
        "signatureMatch": true,
        "completedChunks": 2,
        "completedOutputFrames": 120,
        "nextSourceFrame": 60,
        "totalOutputFrames": 240
    });

    let inspection: ResumeInspectionResult =
        serde_json::from_value(raw.clone()).expect("resume inspection");
    assert_eq!(
        serde_json::to_value(inspection).expect("serialize resume inspection"),
        raw
    );
}

#[test]
fn environment_result_preserves_explicit_collections() {
    let result: EnvironmentCheckResult =
        serde_json::from_value(minimal_environment_result()).expect("minimal environment result");
    let serialized = serde_json::to_value(result).expect("serialize environment result");

    assert_eq!(serialized["ffmpeg"]["hwaccels"], json!([]));
    assert_eq!(serialized["ffmpeg"]["encoderProfiles"], json!([]));
    assert_eq!(serialized["ffmpeg"]["decoderProfiles"], json!([]));
    assert_eq!(serialized["gpu"]["adapters"], json!([]));
    assert_eq!(serialized["tensorEngines"]["pytorch"], json!([]));
    assert_eq!(serialized["tensorEngines"]["paddle"], json!([]));
    assert_eq!(serialized["tensorEngines"]["onnx"], json!([]));
}

#[test]
fn environment_payload_round_trip_uses_checked_at_alias() {
    let raw = json!({
        "result": minimal_environment_result(),
        "source": "cache",
        "checkedAt": "2026-07-28T12:34:56Z"
    });

    let payload: EnvironmentCheckPayload =
        serde_json::from_value(raw.clone()).expect("environment payload");
    assert_eq!(
        serde_json::to_value(payload).expect("serialize environment payload"),
        raw
    );
}

#[test]
fn environment_result_rejects_unknown_fields() {
    let mut raw = minimal_environment_result();
    raw["unexpected"] = json!(true);
    let error = serde_json::from_value::<EnvironmentCheckResult>(raw)
        .expect_err("unknown environment fields must be rejected");
    assert!(error.to_string().contains("unexpected"));
}

#[test]
fn task_progress_omits_absent_metrics_and_preserves_present_metrics() {
    let raw = json!({
        "current": 3,
        "total": 10,
        "percent": 30.0,
        "stage": "interpolation",
        "stageIndex": 1,
        "stageTotal": 2
    });
    let progress: TaskProgressPayload =
        serde_json::from_value(raw.clone()).expect("progress without metrics");
    assert_eq!(
        serde_json::to_value(progress).expect("serialize progress"),
        raw
    );

    let mut with_metrics = raw;
    with_metrics["metrics"] = json!({
        "processedFrames": 3,
        "queues": { "decoded": 2 }
    });
    let progress: TaskProgressPayload =
        serde_json::from_value(with_metrics.clone()).expect("progress with metrics");
    assert_eq!(
        serde_json::to_value(progress).expect("serialize progress metrics"),
        with_metrics
    );
}

#[test]
fn backend_error_conversion_preserves_wire_payload() {
    let raw = json!({
        "code": "invalid_config",
        "message": "invalid workflow",
        "details": { "field": "workflowConfig" }
    });
    let backend: BackendTaskErrorPayload =
        serde_json::from_value(raw.clone()).expect("backend error payload");
    let shell: TaskErrorPayload = backend.into();

    assert_eq!(
        serde_json::to_value(shell).expect("serialize converted error"),
        raw
    );
}

#[test]
fn backend_error_subset_rejects_shell_only_codes() {
    let raw = json!({
        "code": "spawn_failed",
        "message": "cannot start backend"
    });

    assert!(serde_json::from_value::<BackendTaskErrorPayload>(raw).is_err());
}

#[test]
fn generated_persistence_entries_reject_missing_and_extra_fields() {
    let missing_fingerprint = json!({
        "schemaVersion": 14,
        "checkedAt": "2026-07-28T12:34:56Z",
        "result": minimal_environment_result()
    });
    assert!(serde_json::from_value::<EnvironmentCacheEntry>(missing_fingerprint).is_err());

    let mut extra_preset_field = json!({
        "schemaVersion": 2,
        "preset": valid_preset_value()
    });
    extra_preset_field["unexpected"] = json!(true);
    assert!(serde_json::from_value::<WorkbenchPresetEntry>(extra_preset_field).is_err());
}
