use serde_json::Value;

pub(crate) use crate::generated::BackendTaskEnvelope as NdjsonEnvelope;
use crate::models::{
    ResumeStatusPayload, TaskCompletedPayload, TaskErrorCode, TaskErrorPayload, TaskProgressPayload,
};

#[derive(Debug)]
pub(crate) enum ClassifiedLine {
    Empty,
    Progress(TaskProgressPayload),
    Completed(TaskCompletedPayload),
    Error(TaskErrorPayload),
    ResumeStatus(ResumeStatusPayload),
    SchemaMismatch(TaskErrorPayload),
    Log(String),
}

/// Parse and classify a backend stdout line once.
///
/// Both the runtime reader and tests use this function, so schema-drift
/// behavior cannot diverge through a test-only mirror parser.
pub(crate) fn classify_line(line: &str) -> ClassifiedLine {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return ClassifiedLine::Empty;
    }

    match serde_json::from_str::<NdjsonEnvelope>(trimmed) {
        Ok(NdjsonEnvelope::Progress(payload)) => ClassifiedLine::Progress(payload),
        Ok(NdjsonEnvelope::Completed(payload)) => ClassifiedLine::Completed(payload),
        Ok(NdjsonEnvelope::Error(payload)) => ClassifiedLine::Error(payload.into()),
        Ok(NdjsonEnvelope::ResumeStatus(payload)) => ClassifiedLine::ResumeStatus(payload),
        Err(envelope_error) => match serde_json::from_str::<Value>(trimmed) {
            Ok(value) if value.is_object() => {
                let type_field = value.get("type").cloned().unwrap_or(Value::Null);
                ClassifiedLine::SchemaMismatch(TaskErrorPayload {
                    code: TaskErrorCode::SchemaMismatch,
                    message: format!(
                        "Backend emitted an NDJSON object that does not match the IPC schema: {envelope_error}"
                    ),
                    details: Some(serde_json::Map::from_iter([
                        (
                            "rawLine".to_string(),
                            Value::String(trimmed.to_string()),
                        ),
                        ("type".to_string(), type_field),
                    ])),
                })
            }
            Err(_) if trimmed.starts_with('{') => {
                ClassifiedLine::SchemaMismatch(TaskErrorPayload {
                    code: TaskErrorCode::SchemaMismatch,
                    message: format!(
                        "Backend emitted malformed NDJSON that does not match the IPC schema: {envelope_error}"
                    ),
                    details: Some(serde_json::Map::from_iter([(
                        "rawLine".to_string(),
                        Value::String(trimmed.to_string()),
                    )])),
                })
            }
            _ => ClassifiedLine::Log(trimmed.to_string()),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{classify_line, ClassifiedLine, NdjsonEnvelope};
    use crate::models::TaskErrorCode;

    #[test]
    fn trims_free_form_log_lines_before_forwarding() {
        match classify_line("  loading model  \r\n") {
            ClassifiedLine::Log(message) => assert_eq!(message, "loading model"),
            other => panic!("expected log, got {other:?}"),
        }
    }

    #[test]
    fn valid_json_scalar_is_not_mistaken_for_an_ndjson_envelope() {
        match classify_line("42") {
            ClassifiedLine::Log(message) => assert_eq!(message, "42"),
            other => panic!("expected scalar log, got {other:?}"),
        }
    }

    #[test]
    fn valid_json_array_is_forwarded_as_a_log() {
        match classify_line(r#"["diagnostic", 1]"#) {
            ClassifiedLine::Log(message) => assert_eq!(message, r#"["diagnostic", 1]"#),
            other => panic!("expected array log, got {other:?}"),
        }
    }

    #[test]
    fn malformed_object_reports_the_raw_line() {
        let line = r#"{"type":"progress","current":"#;
        match classify_line(line) {
            ClassifiedLine::SchemaMismatch(payload) => {
                assert!(matches!(payload.code, TaskErrorCode::SchemaMismatch));
                assert_eq!(payload.details.expect("details")["rawLine"], line);
            }
            other => panic!("expected schema mismatch, got {other:?}"),
        }
    }

    #[test]
    fn unknown_envelope_reports_the_discriminator() {
        match classify_line(r#"{"type":"future_event","value":1}"#) {
            ClassifiedLine::SchemaMismatch(payload) => {
                let details = payload.details.expect("details");
                assert_eq!(details["type"], "future_event");
                assert_eq!(details["rawLine"], r#"{"type":"future_event","value":1}"#);
            }
            other => panic!("expected schema mismatch, got {other:?}"),
        }
    }

    #[test]
    fn object_without_a_discriminator_reports_null_type() {
        match classify_line(r#"{"message":"missing type"}"#) {
            ClassifiedLine::SchemaMismatch(payload) => {
                assert!(payload.details.expect("details")["type"].is_null());
            }
            other => panic!("expected schema mismatch, got {other:?}"),
        }
    }

    #[test]
    fn typed_backend_error_keeps_code_message_and_details() {
        match classify_line(
            r#"{"type":"error","code":"missing_model","message":"weights missing","details":{"path":"model.pkl"}}"#,
        ) {
            ClassifiedLine::Error(payload) => {
                assert!(matches!(
                    payload.code,
                    crate::models::TaskErrorCode::MissingModel
                ));
                assert_eq!(payload.message, "weights missing");
                assert_eq!(payload.details.expect("details")["path"], "model.pkl");
            }
            other => panic!("expected backend error, got {other:?}"),
        }
    }

    #[test]
    fn malformed_non_object_json_remains_a_log() {
        match classify_line("[unterminated") {
            ClassifiedLine::Log(message) => assert_eq!(message, "[unterminated"),
            other => panic!("expected diagnostic log, got {other:?}"),
        }
    }

    #[test]
    fn json_string_is_preserved_as_log_text() {
        match classify_line(r#""backend diagnostic""#) {
            ClassifiedLine::Log(message) => assert_eq!(message, r#""backend diagnostic""#),
            other => panic!("expected JSON string log, got {other:?}"),
        }
    }

    #[test]
    fn deserializes_progress_variant() {
        let line = r#"{"type":"progress","current":50,"total":100,"percent":50.0,"stage":"Encoding","stageIndex":1,"stageTotal":3}"#;
        let envelope: NdjsonEnvelope = serde_json::from_str(line).expect("parse");
        match envelope {
            NdjsonEnvelope::Progress(payload) => {
                assert_eq!(payload.current, 50);
                assert_eq!(payload.total, 100);
                assert_eq!(payload.stage, "Encoding");
            }
            other => panic!("expected Progress, got {:?}", other),
        }
    }

    #[test]
    fn deserializes_completed_variant() {
        let line = r#"{"type":"completed","outputPath":"D:/out.mp4","processedFrames":480,"timeSeconds":12.5}"#;
        let envelope: NdjsonEnvelope = serde_json::from_str(line).expect("parse");
        match envelope {
            NdjsonEnvelope::Completed(payload) => {
                assert_eq!(payload.output_path, "D:/out.mp4");
                assert_eq!(payload.processed_frames, 480);
                assert!((payload.time_seconds - 12.5).abs() < f64::EPSILON);
            }
            other => panic!("expected Completed, got {:?}", other),
        }
    }

    #[test]
    fn deserializes_error_variant() {
        let line = r#"{"type":"error","code":"missing_ffmpeg","message":"FFmpeg not found","details":null}"#;
        let envelope: NdjsonEnvelope = serde_json::from_str(line).expect("parse");
        match envelope {
            NdjsonEnvelope::Error(payload) => {
                assert_eq!(payload.message, "FFmpeg not found");
            }
            other => panic!("expected Error, got {:?}", other),
        }
    }

    #[test]
    fn deserializes_resume_status_variant() {
        let line = r#"{"type":"resume_status","resumed":true,"completedChunks":3,"completedOutputFrames":300,"startSourceFrame":150,"totalOutputFrames":500}"#;
        let envelope: NdjsonEnvelope = serde_json::from_str(line).expect("parse");
        match envelope {
            NdjsonEnvelope::ResumeStatus(payload) => {
                assert!(payload.resumed);
                assert_eq!(payload.completed_chunks, 3);
                assert_eq!(payload.start_source_frame, 150);
            }
            other => panic!("expected ResumeStatus, got {:?}", other),
        }
    }

    #[test]
    fn rejects_unknown_variant() {
        let line = r#"{"type":"unknown","payload":42}"#;
        let result: Result<NdjsonEnvelope, _> = serde_json::from_str(line);
        assert!(
            result.is_err(),
            "unknown variant should fail to deserialize"
        );
    }

    // Fixture-style integration: simulate a complete NDJSON stream and
    // assert that each line is classified as the stdout reader would.
    // This is the closest we can get to a spawn-level test without mocking
    // tauri's AppHandle.
    // ------------------------------------------------------------------

    #[derive(Debug, Clone, PartialEq, Eq)]
    enum LineClassification {
        Progress,
        Completed,
        Error,
        ResumeStatus,
        SchemaMismatch, // JSON object whose ``type`` we don't recognise
        Log,            // non-JSON text, including ``[VP_PROGRESS]`` lines
        Empty,
    }

    fn classification(line: &str) -> LineClassification {
        match classify_line(line) {
            ClassifiedLine::Empty => LineClassification::Empty,
            ClassifiedLine::Progress(_) => LineClassification::Progress,
            ClassifiedLine::Completed(_) => LineClassification::Completed,
            ClassifiedLine::Error(_) => LineClassification::Error,
            ClassifiedLine::ResumeStatus(_) => LineClassification::ResumeStatus,
            ClassifiedLine::SchemaMismatch(_) => LineClassification::SchemaMismatch,
            ClassifiedLine::Log(_) => LineClassification::Log,
        }
    }

    #[test]
    fn integration_classifies_success_stream() {
        // Models a happy-path task: a few progress beats then completion.
        let stream = concat!(
            r#"{"type":"progress","current":10,"total":100,"percent":10.0,"stage":"Decoding","stageIndex":1,"stageTotal":2}"#,
            "\n",
            "[VP_PROGRESS] 10% 10/100\n",
            "Loading model from /opt/models/rife.onnx\n",
            r#"{"type":"progress","current":50,"total":100,"percent":50.0,"stage":"Encoding","stageIndex":2,"stageTotal":2}"#,
            "\n",
            r#"{"type":"completed","outputPath":"D:/out.mp4","processedFrames":100,"timeSeconds":4.2}"#,
            "\n",
        );

        let classifications: Vec<_> = stream.lines().map(classification).collect();
        assert_eq!(
            classifications,
            vec![
                LineClassification::Progress,
                LineClassification::Log, // VP_PROGRESS terminal bar
                LineClassification::Log, // free-form log line
                LineClassification::Progress,
                LineClassification::Completed,
            ],
            "stream classification drifted; stdout reader and envelope parser disagree"
        );
    }

    #[test]
    fn integration_classifies_resume_then_error_stream() {
        // Models a resume path that subsequently fails — error envelope must
        // still be picked up after the resume_status frame.
        let stream = concat!(
            r#"{"type":"resume_status","resumed":true,"completedChunks":2,"completedOutputFrames":200,"startSourceFrame":120,"totalOutputFrames":500}"#,
            "\n",
            r#"{"type":"progress","current":210,"total":500,"percent":42.0,"stage":"Encoding","stageIndex":1,"stageTotal":1}"#,
            "\n",
            "[VP_PROGRESS] 42% 210/500\n",
            r#"{"type":"error","code":"missing_model","message":"weight file missing","details":{"path":"/opt/models/missing.pkl"}}"#,
            "\n",
        );

        let classifications: Vec<_> = stream.lines().map(classification).collect();
        assert_eq!(
            classifications,
            vec![
                LineClassification::ResumeStatus,
                LineClassification::Progress,
                LineClassification::Log,
                LineClassification::Error,
            ]
        );
    }

    #[test]
    fn integration_treats_malformed_ndjson_as_schema_mismatch() {
        // An object-shaped line is part of the NDJSON protocol surface.
        // Syntax errors must be fatal instead of silently becoming logs.
        let stream = concat!(
            "{\"type\":\"progress\",\"oops\":\n",      // unterminated, not parseable
            "{\"type\":\"unknown_variant\"}\n",         // JSON object, unknown variant
            "not json at all\n",
            "{\"type\":\"completed\",\"outputPath\":\"D:/out.mp4\",\"processedFrames\":1,\"timeSeconds\":0.1}\n",
        );

        let classifications: Vec<_> = stream.lines().map(classification).collect();
        assert_eq!(
            classifications,
            vec![
                LineClassification::SchemaMismatch,
                LineClassification::SchemaMismatch,
                LineClassification::Log,
                LineClassification::Completed,
            ]
        );
    }

    #[test]
    fn integration_flags_envelope_with_missing_required_field_as_schema_mismatch() {
        // Progress envelope missing the mandatory ``stage`` field — valid
        // JSON object but breaks the schema. The classifier makes this loud
        // so backend / Rust drift can't go unnoticed for a whole task.
        let line = r#"{"type":"progress","current":50,"total":100,"percent":50.0}"#;
        assert_eq!(classification(line), LineClassification::SchemaMismatch);
    }

    #[test]
    fn integration_skips_empty_and_whitespace_lines() {
        let stream = "\n   \n\t\n";
        let classifications: Vec<_> = stream.lines().map(classification).collect();
        assert_eq!(classifications, vec![LineClassification::Empty; 3]);
    }
}
