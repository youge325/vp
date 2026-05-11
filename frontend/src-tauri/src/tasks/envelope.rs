use serde::Deserialize;
use serde_json::Value;

use crate::models::{ResumeStatusPayload, TaskCompletedPayload, TaskErrorPayload, TaskProgressPayload};

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NdjsonEnvelope {
    #[serde(rename = "progress")]
    Progress(TaskProgressPayload),
    #[serde(rename = "completed")]
    Completed(TaskCompletedPayload),
    #[serde(rename = "error")]
    Error(TaskErrorPayload),
    #[serde(rename = "resume_status")]
    ResumeStatus(ResumeStatusPayload),
}

pub fn parse_last_json_line(stdout: &str) -> Option<Value> {
    stdout
        .lines()
        .rev()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .and_then(|line| serde_json::from_str::<Value>(line).ok())
}

#[cfg(test)]
mod tests {
    use super::{parse_last_json_line, NdjsonEnvelope};

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
        assert!(result.is_err(), "unknown variant should fail to deserialize");
    }
}
