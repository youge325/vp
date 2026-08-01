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

pub(super) fn deserialize_success_envelope<T: DeserializeOwned>(
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
