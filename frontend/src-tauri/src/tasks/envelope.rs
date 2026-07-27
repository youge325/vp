use serde::Deserialize;
use serde_json::Value;

use crate::models::{
    ResumeStatusPayload, TaskCompletedPayload, TaskErrorPayload, TaskProgressPayload,
};

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub(crate) enum NdjsonEnvelope {
    #[serde(rename = "progress")]
    Progress(TaskProgressPayload),
    #[serde(rename = "completed")]
    Completed(TaskCompletedPayload),
    #[serde(rename = "error")]
    Error(TaskErrorPayload),
    #[serde(rename = "resume_status")]
    ResumeStatus(ResumeStatusPayload),
}

pub(crate) fn parse_last_json_line(stdout: &str) -> Option<Value> {
    stdout
        .lines()
        .rev()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .and_then(|line| serde_json::from_str::<Value>(line).ok())
}

pub(super) fn error_payload_from_value(value: Value) -> Option<TaskErrorPayload> {
    match serde_json::from_value::<NdjsonEnvelope>(value).ok()? {
        NdjsonEnvelope::Error(payload) => Some(payload),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::{error_payload_from_value, parse_last_json_line, NdjsonEnvelope};
    use crate::models::TaskErrorCode;

    #[test]
    fn parses_last_json_line() {
        let stdout = "noise\n{\"type\":\"check\",\"ffmpeg\":{\"available\":true}}\n";
        let parsed = parse_last_json_line(stdout).expect("json");
        assert_eq!(parsed["type"], "check");
    }

    #[test]
    fn parses_last_json_line_returns_none_when_no_json() {
        assert!(parse_last_json_line("noise\nmore noise").is_none());
        assert!(parse_last_json_line("").is_none());
        assert!(parse_last_json_line("   \n   ").is_none());
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
    fn extracts_error_payload_from_the_shared_envelope() {
        let payload = error_payload_from_value(json!({
            "type": "error",
            "code": "missing_ffmpeg",
            "message": "ffmpeg.exe missing",
            "details": null,
        }))
        .expect("error envelope");

        assert!(matches!(payload.code, TaskErrorCode::MissingFfmpeg));
        assert_eq!(payload.message, "ffmpeg.exe missing");
    }

    #[test]
    fn error_payload_extraction_rejects_non_error_envelopes() {
        assert!(error_payload_from_value(json!({
            "type": "completed",
            "outputPath": "D:/out.mp4",
            "processedFrames": 1,
            "timeSeconds": 0.1,
        }))
        .is_none());
    }

    #[test]
    fn error_payload_extraction_rejects_success_payloads_without_a_type() {
        assert!(error_payload_from_value(json!({
            "ffmpeg": { "available": true },
            "gpu": { "available": false },
        }))
        .is_none());
    }

    #[test]
    fn error_payload_extraction_rejects_unknown_error_codes() {
        assert!(error_payload_from_value(json!({
            "type": "error",
            "code": "definitely_not_a_real_code",
            "message": "...",
        }))
        .is_none());
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

    // ------------------------------------------------------------------
    // C.4.5 fixture-style integration: simulate a complete NDJSON stream
    // and assert that each line is classified as the stdout reader would.
    // This is the closest we can get to a spawn-level test without mocking
    // tauri's AppHandle.
    // ------------------------------------------------------------------

    /// Mirrors the dispatch decision tree in
    /// ``runner::spawn_stdout_reader``: parse each line, classify it as
    /// Progress / Completed / ResumeStatus / Error / SchemaMismatch or
    /// fall back to TaskLog.
    ///
    /// Phase D.1.3 — added the ``SchemaMismatch`` arm. JSON objects that
    /// don't match the envelope schema now fail loudly instead of being
    /// silently demoted to log lines.
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

    fn classify_line(line: &str) -> LineClassification {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            return LineClassification::Empty;
        }
        match serde_json::from_str::<NdjsonEnvelope>(trimmed) {
            Ok(NdjsonEnvelope::Progress(_)) => LineClassification::Progress,
            Ok(NdjsonEnvelope::Completed(_)) => LineClassification::Completed,
            Ok(NdjsonEnvelope::Error(_)) => LineClassification::Error,
            Ok(NdjsonEnvelope::ResumeStatus(_)) => LineClassification::ResumeStatus,
            Err(_) => match serde_json::from_str::<serde_json::Value>(trimmed) {
                Ok(value) if value.is_object() => LineClassification::SchemaMismatch,
                _ => LineClassification::Log,
            },
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

        let classifications: Vec<_> = stream.lines().map(classify_line).collect();
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

        let classifications: Vec<_> = stream.lines().map(classify_line).collect();
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
    fn integration_treats_malformed_json_as_log() {
        // A line that looks JSON-ish but has typos must fall through to
        // TaskLog rather than crashing the stdout reader. Phase D.1.3
        // distinguishes "JSON object with unknown ``type``" from "not
        // even parseable JSON" — the former is escalated to SchemaMismatch,
        // the latter is still a plain log line.
        let stream = concat!(
            "{\"type\":\"progress\",\"oops\":\n",      // unterminated, not parseable
            "{\"type\":\"unknown_variant\"}\n",         // JSON object, unknown variant
            "not json at all\n",
            "{\"type\":\"completed\",\"outputPath\":\"D:/out.mp4\",\"processedFrames\":1,\"timeSeconds\":0.1}\n",
        );

        let classifications: Vec<_> = stream.lines().map(classify_line).collect();
        assert_eq!(
            classifications,
            vec![
                LineClassification::Log,
                LineClassification::SchemaMismatch,
                LineClassification::Log,
                LineClassification::Completed,
            ]
        );
    }

    #[test]
    fn integration_flags_envelope_with_missing_required_field_as_schema_mismatch() {
        // Progress envelope missing the mandatory ``stage`` field — valid
        // JSON object but breaks the schema. Phase D.1.3 makes this loud
        // so backend / Rust drift can't go unnoticed for a whole task.
        let line = r#"{"type":"progress","current":50,"total":100,"percent":50.0}"#;
        assert_eq!(classify_line(line), LineClassification::SchemaMismatch);
    }

    #[test]
    fn integration_skips_empty_and_whitespace_lines() {
        let stream = "\n   \n\t\n";
        let classifications: Vec<_> = stream.lines().map(classify_line).collect();
        assert_eq!(classifications, vec![LineClassification::Empty; 3]);
    }
}
