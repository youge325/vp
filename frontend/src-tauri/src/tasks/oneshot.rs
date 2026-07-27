//! One-shot CLI runner for ``check`` / ``info`` / ``inspect-output``.
//!
//! The runner maps backend failures to ``ShellError`` before returning, so
//! command callers only receive success-shaped JSON values.

use std::process::Stdio;

use serde_json::Value;
use tokio::io::AsyncWriteExt;

use crate::error::ShellError;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{apply_no_window, backend_command};
use crate::tasks::envelope::{error_payload_from_value, parse_last_json_line};

/// Run a one-shot CLI subcommand and return its success-shaped JSON value.
///
/// ``args[0]`` is the subcommand name; remaining elements become flag /
/// value pairs (``--input <path>`` style) appended after it.
///
/// ``stdin_payload`` lets callers feed config through stdin instead of
/// command-line flags. ``None`` uses ``Stdio::null`` for commands without
/// input; ``Some`` writes the payload and closes stdin before collecting
/// stdout and stderr.
pub(crate) async fn run_single_cli_command(
    paths: &ResolvedRuntimePaths,
    args: &[String],
    stdin_payload: Option<&str>,
) -> Result<Value, ShellError> {
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
        return match last_json.and_then(error_payload_from_value) {
            Some(envelope) => Err(ShellError::BackendEnvelope {
                code: envelope.code,
                message: envelope.message,
            }),
            None => Err(ShellError::BackendProbeFailed(format!(
                "Backend command failed: {}",
                stderr.trim().trim_matches('"')
            ))),
        };
    }

    last_json.ok_or(ShellError::BackendNoJson)
}
