//! One-shot CLI runner for ``check`` / ``info`` / ``inspect-output``.
//!
//! The runner maps backend failures to ``ShellError`` before returning, so
//! command callers only receive schema-validated success payloads.

use std::fmt;
use std::io;
use std::process::{Output, Stdio};
use std::time::Duration;

use command_group::AsyncGroupChild;
use serde::de::DeserializeOwned;
use serde_json::Value;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::task::JoinHandle;
use tokio::time::{timeout, timeout_at, Instant};

use crate::error::ShellError;
use crate::generated::backend_oneshot_contract;
use crate::models::BackendTaskErrorPayload;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::builder::{backend_command, spawn_no_window_group};
use crate::tasks::envelope::NdjsonEnvelope;
use crate::tasks::subprocess::{
    reap_after_termination_until, request_termination, STDIN_WRITE_TIMEOUT,
    TERMINATION_REAP_TIMEOUT,
};

const INFO_TIMEOUT: Duration = Duration::from_secs(30);
const INSPECT_OUTPUT_TIMEOUT: Duration = Duration::from_secs(60);
const CHECK_TIMEOUT: Duration = Duration::from_secs(180);
const EXIT_POLL_INTERVAL: Duration = Duration::from_millis(10);
#[cfg(test)]
const SPAWN_HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(5);

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

fn deadlines_for_subcommand(subcommand: &str) -> Option<OneShotDeadlines> {
    let total = match subcommand {
        "info" => INFO_TIMEOUT,
        "inspect-output" => INSPECT_OUTPUT_TIMEOUT,
        "check" => CHECK_TIMEOUT,
        _ => return None,
    };
    Some(OneShotDeadlines {
        stdin: STDIN_WRITE_TIMEOUT,
        total,
        termination: TERMINATION_REAP_TIMEOUT,
    })
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

type OutputReader = JoinHandle<io::Result<Vec<u8>>>;

/// Owns every resource associated with a one-shot child.
///
/// The guard is deliberately retained across every await. Dropping the caller's
/// future therefore still synchronously requests group termination and hands
/// the child to a detached reaper instead of relying on PID-only cleanup.
struct BoundedOneShotChild {
    child: Option<AsyncGroupChild>,
    stdout_reader: Option<OutputReader>,
    stderr_reader: Option<OutputReader>,
    termination_timeout: Duration,
}

impl BoundedOneShotChild {
    fn new(mut child: AsyncGroupChild, termination_timeout: Duration) -> Self {
        let stdout_reader = child.inner().stdout.take().map(|mut stdout| {
            tokio::spawn(async move {
                let mut bytes = Vec::new();
                stdout.read_to_end(&mut bytes).await?;
                Ok(bytes)
            })
        });
        let stderr_reader = child.inner().stderr.take().map(|mut stderr| {
            tokio::spawn(async move {
                let mut bytes = Vec::new();
                stderr.read_to_end(&mut bytes).await?;
                Ok(bytes)
            })
        });
        Self {
            child: Some(child),
            stdout_reader,
            stderr_reader,
            termination_timeout,
        }
    }

    #[cfg(test)]
    fn id(&self) -> Option<u32> {
        self.child.as_ref().and_then(AsyncGroupChild::id)
    }

    async fn finish(
        &mut self,
        stdin_payload: Option<Vec<u8>>,
        stdin_timeout: Duration,
    ) -> Result<Output, BoundedCommandError> {
        if self.stdout_reader.is_none() || self.stderr_reader.is_none() {
            return Err(BoundedCommandError::lifecycle(
                "backend one-shot stdout/stderr pipes were not captured",
            ));
        }

        match stdin_payload {
            None => {
                if self
                    .child
                    .as_mut()
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
                    .as_mut()
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

        let status = loop {
            let child = self.child.as_mut().ok_or_else(|| {
                BoundedCommandError::lifecycle(
                    "backend one-shot child was released before it exited",
                )
            })?;
            match child.try_wait() {
                Ok(Some(status)) => break status,
                Ok(None) => tokio::time::sleep(EXIT_POLL_INTERVAL).await,
                Err(error) => {
                    return Err(BoundedCommandError::lifecycle(format!(
                        "unable to wait for backend one-shot process: {error}"
                    )));
                }
            }
        };

        let stdout = await_reader(
            self.stdout_reader
                .take()
                .expect("stdout reader checked above"),
            "stdout",
        )
        .await?;
        let stderr = await_reader(
            self.stderr_reader
                .take()
                .expect("stderr reader checked above"),
            "stderr",
        )
        .await?;
        // `try_wait` above reaped the process group. Disarm the drop path only
        // after both output readers have observed EOF.
        drop(self.child.take());
        Ok(Output {
            status,
            stdout,
            stderr,
        })
    }

    async fn terminate_and_reap(&mut self) -> Result<(), String> {
        let child = self.child.take();
        let stdout_reader = self.stdout_reader.take();
        let stderr_reader = self.stderr_reader.take();
        terminate_and_reap_parts(
            child,
            stdout_reader,
            stderr_reader,
            self.termination_timeout,
        )
        .await
    }
}

impl Drop for BoundedOneShotChild {
    fn drop(&mut self) {
        let Some(mut child) = self.child.take() else {
            return;
        };
        let stdout_reader = self.stdout_reader.take();
        let stderr_reader = self.stderr_reader.take();
        // Synchronously request termination before returning from Drop. The
        // async reaper owns the stable group/job handle from this point on.
        let kill_error = request_termination(&mut child);
        let cleanup_timeout = self.termination_timeout;
        if let Ok(runtime) = tokio::runtime::Handle::try_current() {
            runtime.spawn(async move {
                let _ = terminate_and_reap_parts_after_kill(
                    child,
                    stdout_reader,
                    stderr_reader,
                    cleanup_timeout,
                    kill_error,
                )
                .await;
            });
        }
        // If no runtime exists, dropping `child` still invokes the
        // command-group kill-on-drop fallback. All production call sites run
        // inside Tokio, so the branch above also performs the reap.
    }
}

async fn await_reader(
    reader: OutputReader,
    stream_name: &'static str,
) -> Result<Vec<u8>, BoundedCommandError> {
    reader
        .await
        .map_err(|error| {
            BoundedCommandError::lifecycle(format!(
                "backend one-shot {stream_name} reader stopped: {error}"
            ))
        })?
        .map_err(|error| {
            BoundedCommandError::lifecycle(format!(
                "unable to read backend one-shot {stream_name}: {error}"
            ))
        })
}

async fn terminate_and_reap_parts(
    mut child: Option<AsyncGroupChild>,
    stdout_reader: Option<OutputReader>,
    stderr_reader: Option<OutputReader>,
    cleanup_timeout: Duration,
) -> Result<(), String> {
    let kill_error = child.as_mut().and_then(request_termination);
    match child {
        Some(child) => {
            terminate_and_reap_parts_after_kill(
                child,
                stdout_reader,
                stderr_reader,
                cleanup_timeout,
                kill_error,
            )
            .await
        }
        None => {
            drain_readers(stdout_reader, stderr_reader, cleanup_timeout).await;
            Ok(())
        }
    }
}

async fn terminate_and_reap_parts_after_kill(
    child: AsyncGroupChild,
    stdout_reader: Option<OutputReader>,
    stderr_reader: Option<OutputReader>,
    cleanup_timeout: Duration,
    kill_error: Option<io::Error>,
) -> Result<(), String> {
    let deadline = Instant::now() + cleanup_timeout;
    if let Err(error) =
        reap_after_termination_until(child, deadline, kill_error, "backend one-shot process").await
    {
        abort_readers(stdout_reader, stderr_reader);
        return Err(error);
    }
    drain_readers_until(stdout_reader, stderr_reader, deadline).await;
    Ok(())
}

async fn drain_readers(
    stdout_reader: Option<OutputReader>,
    stderr_reader: Option<OutputReader>,
    timeout_duration: Duration,
) {
    drain_readers_until(
        stdout_reader,
        stderr_reader,
        Instant::now() + timeout_duration,
    )
    .await;
}

async fn drain_readers_until(
    stdout_reader: Option<OutputReader>,
    stderr_reader: Option<OutputReader>,
    deadline: Instant,
) {
    if let Some(mut reader) = stdout_reader {
        if timeout_at(deadline, &mut reader).await.is_err() {
            reader.abort();
        }
    }
    if let Some(mut reader) = stderr_reader {
        if timeout_at(deadline, &mut reader).await.is_err() {
            reader.abort();
        }
    }
}

fn abort_readers(stdout_reader: Option<OutputReader>, stderr_reader: Option<OutputReader>) {
    if let Some(reader) = stdout_reader {
        reader.abort();
    }
    if let Some(reader) = stderr_reader {
        reader.abort();
    }
}

async fn run_bounded_command(
    mut command: tokio::process::Command,
    stdin_payload: Option<Vec<u8>>,
    deadlines: OneShotDeadlines,
    operation: &str,
    #[cfg(test)] spawn_handshake: Option<SpawnHandshake>,
) -> Result<Output, BoundedCommandError> {
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
    let child = spawn_no_window_group(&mut command).map_err(BoundedCommandError::Spawn)?;
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

enum TypedCliEnvelope<T> {
    Success(T),
    Error(BackendTaskErrorPayload),
}

/// Run a generated application IPC command and deserialize its success payload.
///
/// The manifest-owned contract resolves the private backend subcommand.
/// ``extra_args`` contains only command-specific flag/value pairs.
///
/// ``stdin_payload`` lets callers feed config through stdin instead of
/// command-line flags. ``None`` uses ``Stdio::null`` for commands without
/// input; ``Some`` writes the payload and closes stdin before collecting
/// stdout and stderr.
pub(crate) async fn run_single_cli_command<T: DeserializeOwned>(
    paths: &ResolvedRuntimePaths,
    ipc_command: &str,
    extra_args: &[String],
    stdin_payload: Option<&str>,
    payload_name: &'static str,
) -> Result<T, ShellError> {
    let contract = backend_oneshot_contract(ipc_command).ok_or_else(|| {
        ShellError::InvalidInput(format!(
            "application IPC command has no backend one-shot contract: {ipc_command}"
        ))
    })?;
    let deadlines = deadlines_for_subcommand(contract.subcommand).ok_or_else(|| {
        ShellError::InvalidInput(format!(
            "backend one-shot subcommand has no deadline policy: {}",
            contract.subcommand
        ))
    })?;
    let mut command = backend_command(paths, contract.subcommand);
    command.args(extra_args);
    let output = run_bounded_command(
        command,
        stdin_payload.map(|payload| payload.as_bytes().to_vec()),
        deadlines,
        contract.subcommand,
        #[cfg(test)]
        None,
    )
    .await
    .map_err(BoundedCommandError::into_shell_error)?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let last_envelope = parse_last_typed_cli_envelope(
        &stdout,
        contract.envelope,
        contract.preserve_discriminator,
        payload_name,
    )?;

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
    use std::io::Read;
    use std::time::Duration;

    use serde::Deserialize;
    use serde_json::json;
    use tokio::process::Command;
    use tokio::sync::oneshot;

    use super::{
        deadlines_for_subcommand, deserialize_success_envelope, parse_last_typed_cli_envelope,
        run_bounded_command, OneShotDeadlines, SpawnHandshake, TypedCliEnvelope, CHECK_TIMEOUT,
        INFO_TIMEOUT, INSPECT_OUTPUT_TIMEOUT, SPAWN_HANDSHAKE_TIMEOUT,
    };
    use crate::error::ShellError;
    use crate::models::BackendTaskErrorCode;
    use crate::tasks::subprocess::{STDIN_WRITE_TIMEOUT, TERMINATION_REAP_TIMEOUT};
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
        let info = deadlines_for_subcommand("info").expect("info policy");
        let inspect = deadlines_for_subcommand("inspect-output").expect("inspect policy");
        let check = deadlines_for_subcommand("check").expect("check policy");

        assert_eq!(info.stdin, STDIN_WRITE_TIMEOUT);
        assert_eq!(info.total, INFO_TIMEOUT);
        assert_eq!(inspect.total, INSPECT_OUTPUT_TIMEOUT);
        assert_eq!(check.total, CHECK_TIMEOUT);
        assert_eq!(check.termination, TERMINATION_REAP_TIMEOUT);
        assert!(deadlines_for_subcommand("process").is_none());
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
        assert!(String::from_utf8_lossy(&output.stdout).contains("fixture-observed-stdin-eof"));
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
