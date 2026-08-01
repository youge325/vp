//! One-shot CLI runner for ``check`` / ``info`` / ``inspect-output``.
//!
//! The runner maps backend failures to ``ShellError`` before returning, so
//! command callers only receive schema-validated success payloads.

use std::fmt;
use std::io;
use std::process::Stdio;
use std::time::Duration;

use serde::de::DeserializeOwned;
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::process::{ChildStderr, ChildStdout};
use tokio::time::{timeout, timeout_at, Instant};

use crate::error::ShellError;
use crate::generated::{
    BackendOneShotSpec, ERROR_SUMMARY_LIMIT_BYTES, NDJSON_LINE_LIMIT_BYTES,
    ONE_SHOT_STDOUT_LIMIT_BYTES, STDERR_TAIL_LIMIT_BYTES,
};
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::bounded_io::read_bounded_ndjson_output;
use crate::tasks::builder::{backend_command, spawn_no_window_group};
use crate::tasks::oneshot_envelope::{parse_last_typed_cli_envelope, TypedCliEnvelope};
use crate::tasks::stderr::retain_tail;
use crate::tasks::subprocess::{ProcessGroupChild, ProcessGroupOwner, ReapOutcome, ReapTicket};
const EXIT_POLL_INTERVAL: Duration = Duration::from_millis(10);
#[cfg(test)]
const SPAWN_HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug)]
struct BoundedOneShotOutput {
    status: std::process::ExitStatus,
    stdout: String,
    stderr: Vec<u8>,
}

#[cfg(test)]
struct SpawnHandshake {
    started: tokio::sync::oneshot::Sender<u32>,
    release: tokio::sync::oneshot::Receiver<()>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct OneShotDeadlines {
    stdin: Duration,
    total: Duration,
    termination: Duration,
}

fn deadlines_for_spec<S: BackendOneShotSpec>() -> OneShotDeadlines {
    OneShotDeadlines {
        stdin: S::STDIN_TIMEOUT,
        total: S::TOTAL_TIMEOUT,
        termination: S::TERMINATION_TIMEOUT,
    }
}

#[derive(Debug)]
enum BoundedCommandError {
    Spawn(io::Error),
    Lifecycle(String),
}

impl BoundedCommandError {
    fn lifecycle(message: impl Into<String>) -> Self {
        Self::Lifecycle(message.into())
    }

    fn with_cleanup(self, cleanup: Result<(), String>) -> Self {
        match cleanup {
            Ok(()) => self,
            Err(cleanup_error) => {
                Self::Lifecycle(format!("{self}; cleanup failed: {cleanup_error}"))
            }
        }
    }

    fn into_shell_error(self) -> ShellError {
        match self {
            Self::Spawn(error) => ShellError::Spawn(error),
            Self::Lifecycle(message) => ShellError::BackendProbeFailed(message),
        }
    }
}

impl fmt::Display for BoundedCommandError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Spawn(error) => write!(formatter, "unable to spawn backend: {error}"),
            Self::Lifecycle(message) => formatter.write_str(message),
        }
    }
}

/// Owns every resource associated with a one-shot child.
///
/// The guard is deliberately retained across every await. Dropping the caller's
/// future closes both output pipes, synchronously requests group termination,
/// and hands the stable group/job handle to the process cleanup coordinator.
struct BoundedOneShotChild {
    stdout: Option<ChildStdout>,
    stderr: Option<ChildStderr>,
    child: ProcessGroupOwner,
    reap_ticket: Option<ReapTicket>,
    termination_timeout: Duration,
}

impl BoundedOneShotChild {
    fn new(mut child: ProcessGroupChild, termination_timeout: Duration) -> Self {
        let stdout = child.inner().stdout.take();
        let stderr = child.inner().stderr.take();
        let (child, reap_ticket) = ProcessGroupOwner::new(child, "backend one-shot process");
        Self {
            stdout,
            stderr,
            child,
            reap_ticket: Some(reap_ticket),
            termination_timeout,
        }
    }

    #[cfg(test)]
    fn id(&self) -> Option<u32> {
        self.child.id()
    }

    async fn finish(
        &mut self,
        stdin_payload: Option<Vec<u8>>,
        stdin_timeout: Duration,
    ) -> Result<BoundedOneShotOutput, BoundedCommandError> {
        let mut stdout = self.stdout.take().ok_or_else(|| {
            BoundedCommandError::lifecycle("backend one-shot stdout pipe was not captured")
        })?;
        let mut stderr = self.stderr.take().ok_or_else(|| {
            BoundedCommandError::lifecycle("backend one-shot stderr pipe was not captured")
        })?;

        match stdin_payload {
            None => {
                if self
                    .child
                    .inner_mut()
                    .and_then(|child| child.inner().stdin.take())
                    .is_some()
                {
                    return Err(BoundedCommandError::lifecycle(
                        "backend one-shot without a payload unexpectedly captured stdin",
                    ));
                }
            }
            Some(payload) => {
                let mut stdin = self
                    .child
                    .inner_mut()
                    .and_then(|child| child.inner().stdin.take())
                    .ok_or_else(|| {
                        BoundedCommandError::lifecycle(
                            "backend one-shot payload requires a captured stdin pipe",
                        )
                    })?;
                let write = async {
                    stdin.write_all(&payload).await.map_err(|error| {
                        BoundedCommandError::lifecycle(format!(
                            "unable to write backend one-shot stdin: {error}"
                        ))
                    })?;
                    stdin.flush().await.map_err(|error| {
                        BoundedCommandError::lifecycle(format!(
                            "unable to flush backend one-shot stdin: {error}"
                        ))
                    })?;
                    stdin.shutdown().await.map_err(|error| {
                        BoundedCommandError::lifecycle(format!(
                            "unable to close backend one-shot stdin: {error}"
                        ))
                    })
                };
                timeout(stdin_timeout, write).await.map_err(|_| {
                    BoundedCommandError::lifecycle(format!(
                        "backend one-shot stdin timed out after {} seconds",
                        stdin_timeout.as_secs_f64()
                    ))
                })??;
            }
        }

        let (status, stdout, stderr) = {
            let mut status = None;
            let mut stdout_bytes = None;
            let mut stderr_bytes = None;
            let mut wait = Box::pin(wait_for_exit(&mut self.child));
            let mut read_stdout = Box::pin(read_bounded_ndjson_output(
                &mut stdout,
                ONE_SHOT_STDOUT_LIMIT_BYTES,
                NDJSON_LINE_LIMIT_BYTES,
            ));
            let mut read_stderr =
                Box::pin(read_retained_tail(&mut stderr, STDERR_TAIL_LIMIT_BYTES));

            loop {
                tokio::select! {
                    result = &mut wait, if status.is_none() => {
                        status = Some(result?);
                    }
                    result = &mut read_stdout, if stdout_bytes.is_none() => {
                        stdout_bytes = Some(map_reader_result(result, "stdout")?);
                    }
                    result = &mut read_stderr, if stderr_bytes.is_none() => {
                        stderr_bytes = Some(map_reader_result(result, "stderr")?);
                    }
                }
                if let (Some(status), Some(stdout), Some(stderr)) = (
                    status.as_ref(),
                    stdout_bytes.as_mut(),
                    stderr_bytes.as_mut(),
                ) {
                    break (
                        status.to_owned(),
                        std::mem::take(stdout),
                        std::mem::take(stderr),
                    );
                }
            }
        };

        let reap_ticket = self.reap_ticket.take().ok_or_else(|| {
            BoundedCommandError::lifecycle("backend one-shot reap ticket was not retained")
        })?;
        confirm_reaped(&reap_ticket)?;
        Ok(BoundedOneShotOutput {
            status,
            stdout,
            stderr,
        })
    }

    async fn terminate_and_reap(&mut self) -> Result<(), String> {
        self.stdout.take();
        self.stderr.take();
        self.child
            .terminate_and_reap(self.termination_timeout)
            .await?;
        let reap_ticket = self
            .reap_ticket
            .take()
            .ok_or_else(|| "backend one-shot reap ticket was not retained".to_string())?;
        match reap_ticket.current() {
            Some(ReapOutcome::Reaped) => Ok(()),
            Some(ReapOutcome::Failed(error)) => Err(error),
            None => Err("process exited without publishing its reap outcome".to_string()),
        }
    }
}

async fn wait_for_exit(
    child: &mut ProcessGroupOwner,
) -> Result<std::process::ExitStatus, BoundedCommandError> {
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Ok(status),
            Ok(None) => tokio::time::sleep(EXIT_POLL_INTERVAL).await,
            Err(error) => {
                return Err(BoundedCommandError::lifecycle(format!(
                    "unable to wait for backend one-shot process: {error}"
                )));
            }
        }
    }
}

fn confirm_reaped(ticket: &ReapTicket) -> Result<(), BoundedCommandError> {
    match ticket.current() {
        Some(ReapOutcome::Reaped) => Ok(()),
        Some(ReapOutcome::Failed(error)) => Err(BoundedCommandError::lifecycle(error)),
        None => Err(BoundedCommandError::lifecycle(
            "process exited without publishing its reap outcome",
        )),
    }
}

async fn read_retained_tail<R: AsyncRead + Unpin>(
    reader: &mut R,
    limit: usize,
) -> io::Result<Vec<u8>> {
    let mut retained = Vec::with_capacity(limit.min(8192));
    let mut chunk = [0_u8; 8192];
    loop {
        let count = reader.read(&mut chunk).await?;
        if count == 0 {
            return Ok(retained);
        }
        if limit == 0 {
            continue;
        }
        if count >= limit {
            retained.clear();
            retained.extend_from_slice(&chunk[count - limit..count]);
            continue;
        }
        let overflow = retained.len().saturating_add(count).saturating_sub(limit);
        if overflow > 0 {
            retained.drain(..overflow);
        }
        retained.extend_from_slice(&chunk[..count]);
    }
}

fn map_reader_result<T>(
    result: io::Result<T>,
    stream_name: &'static str,
) -> Result<T, BoundedCommandError> {
    result.map_err(|error| {
        BoundedCommandError::lifecycle(format!(
            "unable to read backend one-shot {stream_name}: {error}"
        ))
    })
}

async fn run_bounded_command(
    mut command: tokio::process::Command,
    stdin_payload: Option<Vec<u8>>,
    deadlines: OneShotDeadlines,
    operation: &str,
    #[cfg(test)] spawn_handshake: Option<SpawnHandshake>,
) -> Result<BoundedOneShotOutput, BoundedCommandError> {
    if stdin_payload.is_some() {
        command.stdin(Stdio::piped());
    } else {
        // Commands with no payload must never inherit the desktop host's
        // stdin, otherwise a backend read can keep the command alive forever.
        command.stdin(Stdio::null());
    }
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());

    let started_at = Instant::now();
    let child = match spawn_no_window_group(&mut command) {
        Ok(child) => child,
        Err(error) => {
            let (source, child) = error.into_parts();
            let primary = BoundedCommandError::Spawn(source);
            if let Some(child) = child {
                let mut owner = BoundedOneShotChild::new(child, deadlines.termination);
                return Err(primary.with_cleanup(owner.terminate_and_reap().await));
            }
            return Err(primary);
        }
    };
    let mut child = BoundedOneShotChild::new(child, deadlines.termination);
    #[cfg(test)]
    let started_at = match spawn_handshake {
        Some(handshake) => {
            let pid = child.id().ok_or_else(|| {
                BoundedCommandError::lifecycle("spawned one-shot child did not expose a process id")
            })?;
            handshake.started.send(pid).map_err(|_| {
                BoundedCommandError::lifecycle(
                    "one-shot spawn handshake receiver closed before the process id was published",
                )
            })?;
            timeout(SPAWN_HANDSHAKE_TIMEOUT, handshake.release)
                .await
                .map_err(|_| {
                    BoundedCommandError::lifecycle(
                        "one-shot spawn handshake was not released within 5 seconds",
                    )
                })?
                .map_err(|_| {
                    BoundedCommandError::lifecycle("one-shot spawn handshake release sender closed")
                })?;
            // Test-only coordination isolates the command's total deadline
            // from test-harness process startup. Production always retains
            // the original pre-spawn deadline above.
            Instant::now()
        }
        None => started_at,
    };
    let result = timeout_at(
        started_at + deadlines.total,
        child.finish(stdin_payload, deadlines.stdin),
    )
    .await;

    match result {
        Ok(Ok(output)) => Ok(output),
        Ok(Err(error)) => {
            let cleanup = child.terminate_and_reap().await;
            Err(error.with_cleanup(cleanup))
        }
        Err(_) => {
            let error = BoundedCommandError::lifecycle(format!(
                "backend `{operation}` timed out after {} seconds",
                deadlines.total.as_secs_f64()
            ));
            let cleanup = child.terminate_and_reap().await;
            Err(error.with_cleanup(cleanup))
        }
    }
}

/// Run a generated application IPC command and deserialize its success payload.
///
/// The manifest-owned contract resolves the private backend subcommand.
/// The sealed spec owns the exact argument encoder and optional stdin member,
/// so callers cannot pair a valid command with arbitrary flags or another
/// command's payload type.
pub(crate) async fn run_single_cli_command<S>(
    paths: &ResolvedRuntimePaths,
    invocation: &S::Invocation,
) -> Result<S::Output, ShellError>
where
    S: BackendOneShotSpec,
    S::Output: DeserializeOwned,
{
    let deadlines = deadlines_for_spec::<S>();
    let command = backend_command::<S>(paths, invocation);
    let stdin_payload = S::stdin_payload(invocation)
        .map(serde_json::to_vec)
        .transpose()
        .map_err(|error| {
            ShellError::SchemaValidation(format!(
                "Unable to serialize {} input: {error}",
                S::PAYLOAD_NAME
            ))
        })?;
    let output = run_bounded_command(
        command,
        stdin_payload,
        deadlines,
        S::SUBCOMMAND,
        #[cfg(test)]
        None,
    )
    .await
    .map_err(BoundedCommandError::into_shell_error)?;

    let stdout = output.stdout;
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stderr_summary = retain_tail(stderr.trim().trim_matches('"'), ERROR_SUMMARY_LIMIT_BYTES);
    let last_envelope = parse_last_typed_cli_envelope(
        &stdout,
        S::ENVELOPE,
        S::PRESERVE_DISCRIMINATOR,
        S::PAYLOAD_NAME,
    )?;

    match last_envelope {
        Some(TypedCliEnvelope::Error(envelope)) => Err(ShellError::BackendEnvelope(envelope)),
        Some(TypedCliEnvelope::Success(payload)) => {
            if output.status.success() {
                Ok(payload)
            } else {
                Err(ShellError::BackendProbeFailed(format!(
                    "Backend command failed: {}",
                    stderr_summary
                )))
            }
        }
        None => {
            if output.status.success() {
                Err(ShellError::BackendNoJson)
            } else {
                Err(ShellError::BackendProbeFailed(format!(
                    "Backend command failed: {}",
                    stderr_summary
                )))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use std::io::{Read, Write};
    use std::time::Duration;

    use serde::Deserialize;
    use serde_json::json;
    use tokio::process::Command;
    use tokio::sync::oneshot;

    use super::{
        deadlines_for_spec, read_retained_tail, retain_tail, run_bounded_command,
        spawn_no_window_group, BoundedCommandError, OneShotDeadlines, ProcessGroupOwner,
        ReapOutcome, SpawnHandshake, ERROR_SUMMARY_LIMIT_BYTES, ONE_SHOT_STDOUT_LIMIT_BYTES,
        SPAWN_HANDSHAKE_TIMEOUT,
    };
    use crate::error::ShellError;
    use crate::generated::{CheckEnvironmentSpec, CheckResumeStateSpec, InspectVideoSpec};
    use crate::models::BackendTaskErrorCode;
    use crate::tasks::oneshot_envelope::{
        deserialize_success_envelope, parse_last_typed_cli_envelope, TypedCliEnvelope,
    };
    use crate::tasks::test_support::assert_process_exited;

    const FIXTURE_MODE_ENV: &str = "VP_ONESHOT_TEST_MODE";
    const FIXTURE_TEST_NAME: &str = "tasks::oneshot::tests::oneshot_child_fixture";

    #[derive(Debug, Deserialize, PartialEq, Eq)]
    struct ProbePayload {
        value: u32,
    }

    /// Subprocess fixture invoked through the Rust test harness itself. This
    /// avoids shell quoting, Python availability and platform-specific sleep
    /// executables in lifecycle tests.
    #[test]
    fn oneshot_child_fixture() {
        let Ok(mode) = std::env::var(FIXTURE_MODE_ENV) else {
            return;
        };
        match mode.as_str() {
            "stdin-eof" => {
                let mut byte = [0_u8; 1];
                let count = std::io::stdin()
                    .read(&mut byte)
                    .expect("read fixture stdin");
                assert_eq!(count, 0, "None payload must be connected to null stdin");
                println!("fixture-observed-stdin-eof");
            }
            "sleep" => std::thread::sleep(Duration::from_secs(60)),
            "oversized-stdout" => {
                let bytes = vec![b'x'; ONE_SHOT_STDOUT_LIMIT_BYTES + 1];
                std::io::stdout()
                    .write_all(&bytes)
                    .expect("write oversized fixture stdout");
            }
            other => panic!("unknown one-shot fixture mode: {other}"),
        }
    }

    fn fixture_command(mode: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().expect("current test executable"));
        command.args([
            "--exact",
            FIXTURE_TEST_NAME,
            "--nocapture",
            "--test-threads=1",
        ]);
        command.env(FIXTURE_MODE_ENV, mode);
        command
    }

    fn test_deadlines(stdin: Duration, total: Duration) -> OneShotDeadlines {
        OneShotDeadlines {
            stdin,
            total,
            termination: Duration::from_secs(2),
        }
    }

    fn test_spawn_handshake() -> (SpawnHandshake, oneshot::Receiver<u32>, oneshot::Sender<()>) {
        let (started_tx, started_rx) = oneshot::channel();
        let (release_tx, release_rx) = oneshot::channel();
        (
            SpawnHandshake {
                started: started_tx,
                release: release_rx,
            },
            started_rx,
            release_tx,
        )
    }

    async fn release_spawn_handshake(
        started_rx: oneshot::Receiver<u32>,
        release_tx: oneshot::Sender<()>,
    ) -> u32 {
        let pid = tokio::time::timeout(SPAWN_HANDSHAKE_TIMEOUT, started_rx)
            .await
            .expect("bounded runner must publish its fixture pid")
            .expect("fixture pid sender");
        release_tx
            .send(())
            .expect("release bounded runner after observing fixture pid");
        pid
    }

    #[test]
    fn one_shot_deadlines_match_the_command_policy() {
        let info = deadlines_for_spec::<InspectVideoSpec>();
        let inspect = deadlines_for_spec::<CheckResumeStateSpec>();
        let check = deadlines_for_spec::<CheckEnvironmentSpec>();

        assert_eq!(info.stdin, Duration::from_secs(10));
        assert_eq!(info.total, Duration::from_secs(30));
        assert_eq!(inspect.total, Duration::from_secs(60));
        assert_eq!(check.total, Duration::from_secs(180));
        assert_eq!(check.termination, Duration::from_secs(5));
    }

    #[test]
    fn backend_error_summary_is_bounded_by_the_protocol_limit() {
        let summary = retain_tail(
            &"界".repeat(ERROR_SUMMARY_LIMIT_BYTES),
            ERROR_SUMMARY_LIMIT_BYTES,
        );

        assert!(summary.len() <= ERROR_SUMMARY_LIMIT_BYTES);
        assert!(summary.starts_with("[...truncated]"));
    }

    #[tokio::test]
    async fn stderr_reader_retains_only_the_bounded_tail() {
        let mut input = &b"0123456789"[..];
        let retained = read_retained_tail(&mut input, 4)
            .await
            .expect("bounded stderr tail");
        assert_eq!(retained, b"6789");
    }

    #[tokio::test]
    async fn none_payload_uses_null_stdin() {
        let output = run_bounded_command(
            fixture_command("stdin-eof"),
            None,
            test_deadlines(Duration::from_millis(100), Duration::from_secs(3)),
            "fixture",
            None,
        )
        .await
        .expect("fixture exits after observing EOF");

        assert!(output.status.success());
        assert!(output.stdout.contains("fixture-observed-stdin-eof"));
    }

    #[tokio::test]
    async fn child_that_does_not_read_stdin_is_killed_and_reaped() {
        let command = fixture_command("sleep");
        let payload = vec![b'x'; 16 * 1024 * 1024];
        let (handshake, started_rx, release_tx) = test_spawn_handshake();

        let runner = tokio::spawn(run_bounded_command(
            command,
            Some(payload),
            test_deadlines(Duration::from_millis(500), Duration::from_secs(5)),
            "fixture",
            Some(handshake),
        ));
        let pid = release_spawn_handshake(started_rx, release_tx).await;
        let error = runner
            .await
            .expect("bounded command runner")
            .expect_err("blocked stdin must time out");

        assert!(error.to_string().contains("stdin timed out"));
        assert_process_exited(pid, Duration::from_secs(3)).await;
    }

    #[tokio::test]
    async fn child_that_never_exits_is_killed_and_reaped_at_total_deadline() {
        let command = fixture_command("sleep");
        let (handshake, started_rx, release_tx) = test_spawn_handshake();

        // Observe the fixture while the bounded runner is live. Waiting for the
        // timeout first can let cleanup remove the process before a saturated
        // test harness gets a chance to publish the PID handshake.
        let runner = tokio::spawn(run_bounded_command(
            command,
            None,
            test_deadlines(Duration::from_millis(100), Duration::from_secs(1)),
            "fixture-never-exits",
            Some(handshake),
        ));
        let pid = release_spawn_handshake(started_rx, release_tx).await;
        let error = runner
            .await
            .expect("bounded command runner")
            .expect_err("non-exiting child must time out");

        assert!(error
            .to_string()
            .contains("backend `fixture-never-exits` timed out"));
        assert_process_exited(pid, Duration::from_secs(3)).await;
    }

    #[tokio::test]
    async fn oversized_stdout_fails_early_and_the_child_is_reaped() {
        let command = fixture_command("oversized-stdout");
        let (handshake, started_rx, release_tx) = test_spawn_handshake();
        let runner = tokio::spawn(run_bounded_command(
            command,
            None,
            test_deadlines(Duration::from_millis(100), Duration::from_secs(10)),
            "fixture-oversized-stdout",
            Some(handshake),
        ));
        let pid = release_spawn_handshake(started_rx, release_tx).await;
        let error = runner
            .await
            .expect("bounded command runner")
            .expect_err("oversized stdout must fail");

        assert!(error.to_string().contains("stdout"));
        assert!(error.to_string().contains("contract limit"));
        assert_process_exited(pid, Duration::from_secs(3)).await;
    }

    #[tokio::test]
    async fn dropping_the_run_future_kills_and_reaps_the_process_group() {
        let command = fixture_command("sleep");
        let (handshake, started_rx, release_tx) = test_spawn_handshake();
        let task = tokio::spawn(run_bounded_command(
            command,
            None,
            test_deadlines(Duration::from_millis(100), Duration::from_secs(30)),
            "fixture-drop",
            Some(handshake),
        ));
        let pid = release_spawn_handshake(started_rx, release_tx).await;

        task.abort();
        let join_error = task.await.expect_err("aborted runner");
        assert!(join_error.is_cancelled());
        assert_process_exited(pid, Duration::from_secs(3)).await;
    }

    #[test]
    fn cleanup_failure_is_never_lost_from_the_primary_error() {
        let error = BoundedCommandError::lifecycle("primary lifecycle failure")
            .with_cleanup(Err("reap confirmation failed".to_string()));

        assert_eq!(
            error.to_string(),
            "primary lifecycle failure; cleanup failed: reap confirmation failed"
        );
    }

    #[tokio::test]
    async fn transient_wait_error_does_not_seal_the_late_reap_ticket() {
        let mut command = fixture_command("sleep");
        command
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null());
        let child = spawn_no_window_group(&mut command).expect("spawn transient-error fixture");
        let (mut owner, mut ticket) = ProcessGroupOwner::new(child, "transient wait-error fixture");
        owner.inject_wait_error(std::io::Error::other("injected transient wait error"));

        let error = owner
            .terminate_and_reap(Duration::from_secs(2))
            .await
            .expect_err("injected wait error must surface to the immediate caller");
        assert!(error.contains("injected transient wait error"));
        assert_eq!(ticket.current(), None);

        drop(owner);
        assert_eq!(
            ticket.wait_bounded(Duration::from_secs(3)).await,
            Some(ReapOutcome::Reaped)
        );
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
            false,
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
    fn reverse_scan_returns_the_last_schema_valid_typed_envelope() {
        let stdout = concat!(
            "diagnostic text\n",
            "{\"type\":\"check\",\"value\":42}\n",
            "{\"type\":\"check\",\"value\":\"not-an-integer\"}\n",
        );
        let parsed =
            parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe payload")
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
            parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe payload")
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
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(
            "starting\n42\n",
            "check",
            false,
            "probe",
        )
        .expect("scan");

        assert!(parsed.is_none());
    }

    #[test]
    fn reverse_scan_ignores_unrelated_typed_envelopes() {
        let stdout = concat!(
            "{\"type\":\"progress\",\"value\":7}\n",
            "{\"type\":\"resume_inspection\",\"value\":8}\n",
        );
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe")
            .expect("scan");

        assert!(parsed.is_none());
    }

    #[test]
    fn reverse_scan_prefers_a_newer_success_over_an_older_error() {
        let stdout = concat!(
            "{\"type\":\"error\",\"code\":\"missing_ffmpeg\",\"message\":\"old failure\",\"details\":null}\n",
            "{\"type\":\"check\",\"value\":9}\n",
        );
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe")
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
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe")
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
            false,
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
            false,
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
        let parsed = parse_last_typed_cli_envelope::<ProbePayload>(stdout, "check", false, "probe")
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
    fn check_projection_rejects_a_wrong_discriminator() {
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
