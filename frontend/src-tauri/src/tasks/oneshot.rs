//! One-shot CLI runner for ``check`` / ``info`` / ``inspect-output``.
//!
//! The runner maps backend failures to ``ShellError`` before returning, so
//! command callers only receive schema-validated success payloads.

use std::process::Stdio;

use serde::de::DeserializeOwned;
use serde_json::Value;
use tokio::io::AsyncWriteExt;

use crate::error::ShellError;
use crate::models::BackendTaskErrorPayload;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{apply_no_window, backend_command};
use crate::tasks::envelope::NdjsonEnvelope;

enum TypedCliEnvelope<T> {
    Success(T),
    Error(BackendTaskErrorPayload),
}

/// Run a one-shot CLI subcommand and deserialize its success payload.
///
/// ``args[0]`` is the subcommand name; remaining elements become flag /
/// value pairs (``--input <path>`` style) appended after it.
///
/// ``stdin_payload`` lets callers feed config through stdin instead of
/// command-line flags. ``None`` uses ``Stdio::null`` for commands without
/// input; ``Some`` writes the payload and closes stdin before collecting
/// stdout and stderr.
pub(crate) async fn run_single_cli_command<T: DeserializeOwned>(
    paths: &ResolvedRuntimePaths,
    args: &[String],
    stdin_payload: Option<&str>,
    payload_name: &'static str,
) -> Result<T, ShellError> {
    let (subcommand, extra_args) = args.split_first().ok_or_else(|| {
        ShellError::InvalidInput("run_single_cli_command requires a subcommand".to_string())
    })?;
    let mut command = backend_command(paths, subcommand);
    command.args(extra_args);
    apply_no_window(&mut command);

    let output = match stdin_payload {
        None => {
            command.stdin(Stdio::null());
            command.output().await.map_err(ShellError::Spawn)?
        }
        Some(payload) => {
            command.stdin(Stdio::piped());
            command.stdout(Stdio::piped());
            command.stderr(Stdio::piped());
            let mut child = command.spawn().map_err(ShellError::Spawn)?;
            if let Some(mut stdin) = child.stdin.take() {
                // Write the entire payload then drop stdin to signal EOF.
                // Errors here typically mean the child died before reading
                // — let the wait below surface the real error message.
                let _ = stdin.write_all(payload.as_bytes()).await;
                let _ = stdin.flush().await;
            }
            child.wait_with_output().await.map_err(ShellError::Spawn)?
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let expected_type = match subcommand.as_str() {
        "inspect-output" => "resume_inspection",
        other => other,
    };
    let last_envelope = parse_last_typed_cli_envelope(&stdout, expected_type, payload_name)?;

    match last_envelope {
        Some(TypedCliEnvelope::Error(envelope)) => Err(ShellError::BackendEnvelope(envelope)),
        Some(TypedCliEnvelope::Success(payload)) => {
            if output.status.success() {
                Ok(payload)
            } else {
                Err(ShellError::BackendProbeFailed(format!(
                    "Backend command failed: {}",
                    stderr.trim().trim_matches('"')
                )))
            }
        }
        None => {
            if output.status.success() {
                Err(ShellError::BackendNoJson)
            } else {
                Err(ShellError::BackendProbeFailed(format!(
                    "Backend command failed: {}",
                    stderr.trim().trim_matches('"')
                )))
            }
        }
    }
}

fn parse_last_typed_cli_envelope<T: DeserializeOwned>(
    stdout: &str,
    expected_type: &str,
    payload_name: &'static str,
) -> Result<Option<TypedCliEnvelope<T>>, ShellError> {
    let mut newest_schema_error = None;
    for line in stdout
        .lines()
        .rev()
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let Ok(value) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        let Some(kind) = value.get("type").and_then(Value::as_str) else {
            continue;
        };
        if kind == "error" {
            match serde_json::from_value::<NdjsonEnvelope>(value) {
                Ok(NdjsonEnvelope::Error(payload)) => {
                    return Ok(Some(TypedCliEnvelope::Error(payload)));
                }
                Ok(_) => unreachable!("the inspected discriminator was `error`"),
                Err(error) => {
                    newest_schema_error.get_or_insert_with(|| {
                        ShellError::SchemaValidation(format!(
                            "Unable to deserialize backend error envelope: {error}"
                        ))
                    });
                }
            }
        } else if kind == expected_type {
            match deserialize_success_envelope(value, expected_type, payload_name) {
                Ok(payload) => return Ok(Some(TypedCliEnvelope::Success(payload))),
                Err(error) => {
                    newest_schema_error.get_or_insert(error);
                }
            }
        }
    }

    match newest_schema_error {
        Some(error) => Err(error),
        None => Ok(None),
    }
}

fn deserialize_success_envelope<T: DeserializeOwned>(
    mut envelope: Value,
    expected_type: &str,
    payload_name: &'static str,
) -> Result<T, ShellError> {
    // `check` and `info` use a discriminated one-shot envelope whose payload
    // DTO deliberately excludes the transport-only `type` property. Keep
    // `resume_inspection.type`: it is part of that command's public result.
    if matches!(expected_type, "check" | "info") {
        let object = envelope.as_object_mut().ok_or_else(|| {
            ShellError::SchemaValidation(format!(
                "Unable to deserialize {payload_name}: expected an object envelope"
            ))
        })?;
        match object.remove("type") {
            Some(Value::String(kind)) if kind == expected_type => {}
            Some(other) => {
                return Err(ShellError::SchemaValidation(format!(
                    "Unable to deserialize {payload_name}: expected envelope type {expected_type:?}, got {other}"
                )));
            }
            None => {
                return Err(ShellError::SchemaValidation(format!(
                    "Unable to deserialize {payload_name}: missing envelope type"
                )));
            }
        }
    }

    serde_json::from_value(envelope).map_err(|error| {
        ShellError::SchemaValidation(format!("Unable to deserialize {payload_name}: {error}"))
    })
}

#[cfg(test)]
mod tests {
    use serde::Deserialize;
    use serde_json::json;

    use super::{deserialize_success_envelope, parse_last_typed_cli_envelope, TypedCliEnvelope};
    use crate::error::ShellError;
    use crate::models::BackendTaskErrorCode;

    #[derive(Debug, Deserialize, PartialEq, Eq)]
    struct ProbePayload {
        value: u32,
    }

    #[test]
    fn deserializes_typed_success_payload() {
        let payload = deserialize_success_envelope::<ProbePayload>(
            json!({ "type": "check", "value": 42 }),
            "check",
            "probe payload",
        )
        .expect("typed payload");

        assert_eq!(payload, ProbePayload { value: 42 });
    }

    #[test]
    fn maps_success_schema_mismatch_with_payload_name() {
        let error = deserialize_success_envelope::<ProbePayload>(
            json!({ "type": "check", "value": "invalid" }),
            "check",
            "probe payload",
        )
        .expect_err("schema mismatch");

        match error {
            ShellError::SchemaValidation(message) => {
                assert!(message.starts_with("Unable to deserialize probe payload:"));
            }
            other => panic!("unexpected error: {other:?}"),
        }
    }

    #[test]
    fn projects_real_check_envelope_before_strict_payload_decode() {
        #[derive(Debug, Deserialize, PartialEq, Eq)]
        #[serde(rename_all = "camelCase", deny_unknown_fields)]
        struct CheckPayload {
            runtime_mode: String,
        }

        let payload = deserialize_success_envelope::<CheckPayload>(
            json!({ "type": "check", "runtimeMode": "bundled" }),
            "check",
            "environment check result",
        )
        .expect("check payload");
        assert_eq!(payload.runtime_mode, "bundled");
    }

    #[test]
    fn projects_real_info_envelope_before_strict_payload_decode() {
        #[derive(Debug, Deserialize, PartialEq)]
        #[serde(rename_all = "camelCase", deny_unknown_fields)]
        struct InfoPayload {
            fps: f64,
            width: u32,
            height: u32,
            video_codec: String,
        }

        let payload = deserialize_success_envelope::<InfoPayload>(
            json!({
                "type": "info",
                "fps": 24.0,
                "width": 1920,
                "height": 1080,
                "videoCodec": "h264"
            }),
            "info",
            "video info",
        )
        .expect("info payload");
        assert_eq!(payload.video_codec, "h264");
    }

    #[test]
    fn preserves_resume_inspection_discriminant() {
        #[derive(Debug, Deserialize, PartialEq, Eq)]
        #[serde(deny_unknown_fields)]
        struct InspectionPayload {
            r#type: String,
            pipeline_kind: String,
        }

        let payload = deserialize_success_envelope::<InspectionPayload>(
            json!({
                "type": "resume_inspection",
                "pipeline_kind": "streaming"
            }),
            "resume_inspection",
            "resume inspection",
        )
        .expect("resume inspection payload");
        assert_eq!(payload.r#type, "resume_inspection");
    }

    #[test]
    fn reverse_scan_returns_the_last_schema_valid_typed_envelope() {
        let stdout = concat!(
            "diagnostic text\n",
            "{\"type\":\"check\",\"value\":42}\n",
            "{\"type\":\"check\",\"value\":\"not-an-integer\"}\n",
        );
        let parsed =
            parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe payload")
                .expect("scan")
                .expect("typed envelope");
        match parsed {
            TypedCliEnvelope::Success(payload) => assert_eq!(payload, ProbePayload { value: 42 }),
            TypedCliEnvelope::Error(_) => panic!("expected success"),
        }
    }

    #[test]
    fn reverse_scan_preserves_a_backend_error_envelope() {
        let stdout = concat!(
            "{\"type\":\"check\",\"value\":42}\n",
            "{\"type\":\"error\",\"code\":\"missing_ffmpeg\",\"message\":\"missing\",\"details\":{\"path\":\"ffmpeg\"}}\n",
        );
        let parsed =
            parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe payload")
                .expect("scan")
                .expect("typed envelope");
        match parsed {
            TypedCliEnvelope::Error(payload) => {
                assert!(matches!(payload.code, BackendTaskErrorCode::MissingFfmpeg));
                assert_eq!(payload.details.expect("details")["path"], "ffmpeg");
            }
            TypedCliEnvelope::Success(_) => panic!("expected backend error"),
        }
    }

    #[test]
    fn reverse_scan_returns_none_when_stdout_has_only_diagnostics() {
        let parsed =
            parse_last_typed_cli_envelope::<ProbePayload>("starting\n42\n", "check", "probe")
                .expect("scan");

        assert!(parsed.is_none());
    }

    #[test]
    fn reverse_scan_ignores_unrelated_typed_envelopes() {
        let stdout = concat!(
            "{\"type\":\"progress\",\"value\":7}\n",
            "{\"type\":\"resume_inspection\",\"value\":8}\n",
        );
        let parsed =
            parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe").expect("scan");

        assert!(parsed.is_none());
    }

    #[test]
    fn reverse_scan_prefers_a_newer_success_over_an_older_error() {
        let stdout = concat!(
            "{\"type\":\"error\",\"code\":\"missing_ffmpeg\",\"message\":\"old failure\",\"details\":null}\n",
            "{\"type\":\"check\",\"value\":9}\n",
        );
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe")
            .expect("scan")
            .expect("typed envelope");

        match parsed {
            TypedCliEnvelope::Success(payload) => assert_eq!(payload.value, 9),
            TypedCliEnvelope::Error(_) => panic!("newer success must win"),
        }
    }

    #[test]
    fn unrelated_newer_envelope_does_not_hide_an_expected_success() {
        let stdout = concat!(
            "{\"type\":\"check\",\"value\":11}\n",
            "{\"type\":\"progress\",\"current\":1}\n",
        );
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe")
            .expect("scan")
            .expect("typed envelope");

        match parsed {
            TypedCliEnvelope::Success(payload) => assert_eq!(payload.value, 11),
            TypedCliEnvelope::Error(_) => panic!("expected success"),
        }
    }

    #[test]
    fn malformed_expected_envelope_is_reported_when_no_valid_candidate_exists() {
        let error = parse_last_typed_cli_envelope::<ProbePayload>(
            "{\"type\":\"check\",\"value\":\"wrong\"}\n",
            "check",
            "environment check",
        )
        .err()
        .expect("schema mismatch");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message)
                if message.starts_with("Unable to deserialize environment check:")
        ));
    }

    #[test]
    fn malformed_backend_error_is_reported_when_no_valid_candidate_exists() {
        let error = parse_last_typed_cli_envelope::<ProbePayload>(
            "{\"type\":\"error\",\"code\":\"missing_ffmpeg\"}\n",
            "check",
            "probe",
        )
        .err()
        .expect("schema mismatch");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message)
                if message.starts_with("Unable to deserialize backend error envelope:")
        ));
    }

    #[test]
    fn older_valid_success_survives_a_newer_malformed_error_candidate() {
        let stdout = concat!(
            "{\"type\":\"check\",\"value\":17}\n",
            "{\"type\":\"error\",\"code\":\"missing_ffmpeg\"}\n",
        );
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", "probe")
            .expect("valid candidate should win")
            .expect("typed envelope");

        match parsed {
            TypedCliEnvelope::Success(payload) => assert_eq!(payload.value, 17),
            TypedCliEnvelope::Error(_) => {
                panic!("malformed error must not become an error payload")
            }
        }
    }

    #[test]
    fn check_projection_rejects_a_missing_discriminator() {
        let error =
            deserialize_success_envelope::<ProbePayload>(json!({ "value": 42 }), "check", "probe")
                .expect_err("missing type");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message) if message.contains("missing envelope type")
        ));
    }

    #[test]
    fn check_projection_rejects_a_wrong_discriminator() {
        let error = deserialize_success_envelope::<ProbePayload>(
            json!({ "type": "info", "value": 42 }),
            "check",
            "probe",
        )
        .expect_err("wrong type");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message)
                if message.contains("expected envelope type \"check\"")
                    && message.contains("\"info\"")
        ));
    }
}
