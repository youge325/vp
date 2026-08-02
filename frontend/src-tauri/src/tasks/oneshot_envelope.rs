//! Strict reverse-scan parsing for typed one-shot backend envelopes.

use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::error::ShellError;
use crate::models::BackendTaskErrorPayload;
use crate::tasks::envelope::NdjsonEnvelope;

pub(super) enum TypedCliEnvelope<T> {
    Success(T),
    Error(BackendTaskErrorPayload),
}

pub(super) fn parse_last_typed_cli_envelope<T: DeserializeOwned>(
    stdout: &str,
    expected_type: &str,
    preserve_discriminator: bool,
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
            match deserialize_success_envelope(
                value,
                expected_type,
                preserve_discriminator,
                payload_name,
            ) {
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
    preserve_discriminator: bool,
    payload_name: &'static str,
) -> Result<T, ShellError> {
    // `check` and `info` use a discriminated one-shot envelope whose payload
    // DTO deliberately excludes the transport-only `type` property. Keep
    // `resume_inspection.type`: it is part of that command's public result.
    if !preserve_discriminator {
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

    use super::deserialize_success_envelope;
    use crate::error::ShellError;

    #[derive(Debug, Deserialize, PartialEq, Eq)]
    struct ProbePayload {
        value: u32,
    }

    #[test]
    fn deserializes_typed_success_payload() {
        let payload = deserialize_success_envelope::<ProbePayload>(
            json!({ "type": "check", "value": 42 }),
            "check",
            false,
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
            false,
            "probe payload",
        )
        .expect_err("schema mismatch");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message)
                if message.starts_with("Unable to deserialize probe payload:")
        ));
    }

    #[test]
    fn projects_check_envelope_before_strict_payload_decode() {
        #[derive(Debug, Deserialize, PartialEq, Eq)]
        #[serde(rename_all = "camelCase", deny_unknown_fields)]
        struct CheckPayload {
            runtime_mode: String,
        }

        let payload = deserialize_success_envelope::<CheckPayload>(
            json!({ "type": "check", "runtimeMode": "bundled" }),
            "check",
            false,
            "environment check result",
        )
        .expect("check payload");
        assert_eq!(payload.runtime_mode, "bundled");
    }

    #[test]
    fn projects_info_envelope_before_strict_payload_decode() {
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
            false,
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
            true,
            "resume inspection",
        )
        .expect("resume inspection payload");
        assert_eq!(payload.r#type, "resume_inspection");
    }

    #[test]
    fn rejects_a_missing_discriminator() {
        let error = deserialize_success_envelope::<ProbePayload>(
            json!({ "value": 42 }),
            "check",
            false,
            "probe",
        )
        .expect_err("missing type");

        assert!(matches!(
            error,
            ShellError::SchemaValidation(message) if message.contains("missing envelope type")
        ));
    }

    #[test]
    fn rejects_a_wrong_discriminator() {
        let error = deserialize_success_envelope::<ProbePayload>(
            json!({ "type": "info", "value": 42 }),
            "check",
            false,
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
