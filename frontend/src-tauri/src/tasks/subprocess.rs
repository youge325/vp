//! Shared bounded subprocess lifecycle policy.
//!
//! Long-running tasks and one-shot probes both use the same stdin and
//! termination deadlines.  Reaping always retains the command-group/job
//! handle, so cleanup never falls back to a stale numeric process id.

use std::io;
use std::time::Duration;

use command_group::AsyncGroupChild;
use tokio::time::Instant;

pub(super) const STDIN_WRITE_TIMEOUT: Duration = Duration::from_secs(10);
pub(super) const TERMINATION_REAP_TIMEOUT: Duration = Duration::from_secs(5);

const EXIT_POLL_INTERVAL: Duration = Duration::from_millis(10);

pub(super) fn request_termination(child: &mut AsyncGroupChild) -> Option<io::Error> {
    child.start_kill().err()
}

pub(super) async fn terminate_and_reap(
    mut child: AsyncGroupChild,
    timeout: Duration,
    label: &'static str,
) -> Result<(), String> {
    let kill_error = request_termination(&mut child);
    reap_after_termination_until(child, Instant::now() + timeout, kill_error, label).await
}

pub(super) async fn reap_after_termination_until(
    mut child: AsyncGroupChild,
    deadline: Instant,
    kill_error: Option<io::Error>,
    label: &'static str,
) -> Result<(), String> {
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return Ok(()),
            Ok(None) if Instant::now() < deadline => {
                tokio::time::sleep(EXIT_POLL_INTERVAL).await;
            }
            Ok(None) => {
                return Err(format!(
                    "timed out while reaping {label}{}",
                    format_kill_error(kill_error.as_ref())
                ));
            }
            Err(wait_error) => {
                return Err(format!(
                    "unable to reap {label}: {wait_error}{}",
                    format_kill_error(kill_error.as_ref())
                ));
            }
        }
    }
}

pub(super) fn spawn_detached_reaper(
    mut child: AsyncGroupChild,
    timeout: Duration,
    label: &'static str,
) {
    let kill_error = request_termination(&mut child);
    tauri::async_runtime::spawn(async move {
        let _ =
            reap_after_termination_until(child, Instant::now() + timeout, kill_error, label).await;
    });
}

fn format_kill_error(kill_error: Option<&io::Error>) -> String {
    kill_error
        .map(|error| format!("; termination request failed: {error}"))
        .unwrap_or_default()
}
