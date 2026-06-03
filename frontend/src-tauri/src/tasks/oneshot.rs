//! One-shot CLI runner for ``check`` / ``info`` / ``inspect-output``.
//!
//! Split out of the legacy ``tasks::runner`` mod in Phase 5b/c.
//!
//! Phase 5c introduces the [`CliOutcome`] enum so callers must explicitly
//! ``match`` on success / structured-error / unstructured-error variants.
//! Previously the runner returned ``Result<Value, ShellError>`` and
//! happily packaged a backend error envelope as ``Ok(value)`` when the
//! process exited non-zero — silently flipping the outcome's meaning the
//! moment a downstream caller tried to deserialize the value as a
//! success-shaped struct (e.g. ``EnvironmentCheckResult``). With the
//! three-way enum a missed branch becomes a rustc error rather than a
//! quiet schema mismatch at runtime.

use std::process::Stdio;

use serde::Deserialize;
use serde_json::Value;
use tauri::{AppHandle, Runtime};
use tokio::io::AsyncWriteExt;

use crate::error::ShellError;
use crate::models::TaskErrorPayload;
use crate::protocol::TaskErrorCode;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{apply_no_window, backend_command};
use crate::tasks::envelope::parse_last_json_line;

/// Result classification for [`run_single_cli_command`].
#[derive(Debug)]
pub enum CliOutcome {
    /// The process exited 0 and the last JSON line on stdout decoded
    /// successfully. The caller is responsible for further validation
    /// (typed deserialization, etc.).
    Ok(Value),
    /// The process exited non-zero and the last JSON line decoded as a
    /// proper ``{"type":"error", code, message, details}`` envelope.
    /// The frontend can route on ``payload.code`` directly.
    FailedWithEnvelope(TaskErrorPayload),
    /// The process exited non-zero and we could not recover an
    /// envelope — the payload is the trimmed stderr summary so the
    /// user at least sees what the backend printed.
    FailedWithoutEnvelope(String),
}

impl CliOutcome {
    /// Phase 2.2 — 将三种 outcome 变体折叠为 ``Result<Value, ShellError>``。
    /// 消除 ``tasks/commands.rs`` 与 ``services/environment_service.rs`` 的重复
    /// match 逻辑,使信封折叠语义单点维护。
    pub fn into_result(self) -> Result<Value, ShellError> {
        match self {
            Self::Ok(value) => Ok(value),
            Self::FailedWithEnvelope(envelope) => Err(ShellError::BackendEnvelope {
                code: envelope.code,
                message: envelope.message,
            }),
            Self::FailedWithoutEnvelope(message) => Err(ShellError::BackendProbeFailed(message)),
        }
    }
}

/// Lightweight shape probe used to decide whether ``last_json_line`` is
/// a real error envelope or just success-shaped data that happens to
/// be valid JSON. Mirrors the Python emission in ``backend/app/__main__.py``.
#[derive(Debug, Deserialize)]
struct ErrorEnvelopeProbe {
    #[serde(rename = "type")]
    kind: String,
    code: TaskErrorCode,
    message: String,
    #[serde(default)]
    details: Option<Value>,
}

fn try_parse_error_envelope(value: &Value) -> Option<TaskErrorPayload> {
    let probe = serde_json::from_value::<ErrorEnvelopeProbe>(value.clone()).ok()?;
    if probe.kind != "error" {
        return None;
    }
    Some(TaskErrorPayload {
        code: probe.code,
        message: probe.message,
        details: probe.details,
    })
}

/// Run a one-shot CLI subcommand and classify the outcome.
///
/// ``args[0]`` is the subcommand name; remaining elements become flag /
/// value pairs (``--input <path>`` style) appended after it.
///
/// Phase D.3.1 — ``stdin_payload`` lets callers feed config through
/// stdin instead of command-line flags. ``None`` keeps the legacy
/// ``Stdio::null`` behaviour for subcommands that don't take input
/// (e.g. ``check``, ``info``). When ``Some(payload)`` is provided the
/// command is spawned manually (instead of ``Command::output``), the
/// payload is written to stdin, the handle is dropped to signal EOF,
/// and stdout/stderr are then drained synchronously.
pub async fn run_single_cli_command<R: Runtime>(
    app: &AppHandle<R>,
    paths: &ResolvedRuntimePaths,
    args: &[String],
    stdin_payload: Option<&str>,
) -> Result<CliOutcome, ShellError> {
    let _ = app; // Reserved for future per-app log routing.

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
    let last_json = parse_last_json_line(&stdout);

    if !output.status.success() {
        return Ok(
            match last_json.as_ref().and_then(try_parse_error_envelope) {
                Some(envelope) => CliOutcome::FailedWithEnvelope(envelope),
                None => CliOutcome::FailedWithoutEnvelope(format!(
                    "Backend command failed: {}",
                    stderr.trim().trim_matches('"')
                )),
            },
        );
    }

    last_json
        .map(CliOutcome::Ok)
        .ok_or_else(|| ShellError::BackendNoJson)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn envelope_probe_accepts_error_type_tag() {
        let value = json!({
            "type": "error",
            "code": "missing_ffmpeg",
            "message": "ffmpeg.exe missing",
            "details": null,
        });
        let envelope = try_parse_error_envelope(&value).expect("envelope must parse");
        assert!(matches!(envelope.code, TaskErrorCode::MissingFfmpeg));
        assert_eq!(envelope.message, "ffmpeg.exe missing");
    }

    #[test]
    fn envelope_probe_rejects_non_error_type() {
        let value = json!({
            "type": "completed",
            "code": "missing_ffmpeg",
            "message": "irrelevant",
        });
        assert!(try_parse_error_envelope(&value).is_none());
    }

    #[test]
    fn envelope_probe_rejects_success_shape_without_type_field() {
        // ``check`` / ``info`` success payloads have no ``type`` and no
        // ``code`` keys — must not be misclassified as an envelope.
        let value = json!({
            "ffmpeg": { "available": true },
            "gpu": { "available": false },
        });
        assert!(try_parse_error_envelope(&value).is_none());
    }

    #[test]
    fn envelope_probe_rejects_payload_with_unknown_code_string() {
        // Defensive: an envelope with a misspelled / out-of-band code
        // string fails to parse as ``TaskErrorCode`` and therefore
        // falls through to ``FailedWithoutEnvelope`` rather than
        // silently being treated as success.
        let value = json!({
            "type": "error",
            "code": "definitely_not_a_real_code",
            "message": "...",
        });
        assert!(try_parse_error_envelope(&value).is_none());
    }
}
