//! Shared bounded subprocess lifecycle policy.
//!
//! Long-running tasks and one-shot probes both use the same stdin and
//! termination deadlines. Reaping always retains the process-group/job
//! handle, so cleanup never falls back to a stale numeric process id.

use std::io;
use std::process::ExitStatus;
use std::sync::{mpsc, Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant as StdInstant};

use tokio::process::{Child, Command};
use tokio::sync::watch;
use tokio::time::Instant;

use crate::generated::{BackendProcessSpec, StartTaskSpec};

const EXIT_POLL_INTERVAL: Duration = Duration::from_millis(10);

#[cfg(all(test, windows))]
std::thread_local! {
    static WINDOWS_SPAWN_FAILPOINT: std::cell::Cell<u8> = const { std::cell::Cell::new(0) };
}

/// Repository-owned process-group/job handle.
///
/// `tokio::process::Child::try_wait` observes only the process leader. This
/// wrapper additionally retains the stable POSIX process-group identity or
/// Windows job handle and reports exit only after the entire group is empty.
pub(super) struct ProcessGroupChild {
    child: Child,
    leader_status: Option<ExitStatus>,
    #[cfg(target_os = "linux")]
    group: Option<crate::process_control::StableProcessGroup>,
    #[cfg(target_os = "linux")]
    pgid: i32,
    #[cfg(all(unix, not(target_os = "linux")))]
    pgid: i32,
    #[cfg(windows)]
    job: std::os::windows::io::OwnedHandle,
    #[cfg(windows)]
    job_assigned: bool,
}

#[derive(Debug)]
pub(super) struct ProcessGroupSpawnError {
    source: io::Error,
    child: Option<Box<ProcessGroupChild>>,
}

impl ProcessGroupSpawnError {
    pub(super) fn into_parts(self) -> (io::Error, Option<ProcessGroupChild>) {
        (self.source, self.child.map(|child| *child))
    }
}

impl std::fmt::Display for ProcessGroupSpawnError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.source.fmt(formatter)
    }
}

impl std::error::Error for ProcessGroupSpawnError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.source)
    }
}

impl std::fmt::Debug for ProcessGroupChild {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("ProcessGroupChild")
            .field("pid", &self.child.id())
            .field("leader_status", &self.leader_status)
            .finish_non_exhaustive()
    }
}

impl ProcessGroupChild {
    #[cfg(unix)]
    pub(super) fn spawn(command: &mut Command) -> Result<Self, ProcessGroupSpawnError> {
        unsafe {
            command.pre_exec(|| {
                if libc::setpgid(0, 0) == 0 {
                    Ok(())
                } else {
                    Err(io::Error::last_os_error())
                }
            });
        }
        command.kill_on_drop(true);
        let child = command.spawn().map_err(|source| ProcessGroupSpawnError {
            source,
            child: None,
        })?;
        let pgid = child
            .id()
            .and_then(|pid| i32::try_from(pid).ok())
            .ok_or_else(|| ProcessGroupSpawnError {
                source: io::Error::other("spawned process group has no valid leader id"),
                child: None,
            })?;
        #[cfg(target_os = "linux")]
        let group = match crate::process_control::StableProcessGroup::capture(pgid as u32) {
            Ok(group) => Some(group),
            Err(error) => {
                let owner = Self {
                    child,
                    leader_status: None,
                    group: None,
                    pgid,
                };
                return Err(ProcessGroupSpawnError {
                    source: io::Error::other(error.to_string()),
                    child: Some(Box::new(owner)),
                });
            }
        };
        Ok(Self {
            child,
            leader_status: None,
            #[cfg(target_os = "linux")]
            group,
            pgid,
        })
    }

    #[cfg(windows)]
    pub(super) fn spawn(command: &mut Command) -> Result<Self, ProcessGroupSpawnError> {
        use std::mem::size_of;
        use std::os::windows::io::{FromRawHandle, OwnedHandle};
        use std::ptr;

        use windows_sys::Win32::System::JobObjects::{
            CreateJobObjectW, JobObjectExtendedLimitInformation, SetInformationJobObject,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        };
        use windows_sys::Win32::System::Threading::{CREATE_NO_WINDOW, CREATE_SUSPENDED};

        let raw_job = unsafe { CreateJobObjectW(ptr::null(), ptr::null()) };
        if raw_job.is_null() {
            return Err(ProcessGroupSpawnError {
                source: io::Error::last_os_error(),
                child: None,
            });
        }
        let job = unsafe { OwnedHandle::from_raw_handle(raw_job) };
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let configured = unsafe {
            SetInformationJobObject(
                raw_job,
                JobObjectExtendedLimitInformation,
                (&raw const limits).cast(),
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        };
        if configured == 0 {
            return Err(ProcessGroupSpawnError {
                source: io::Error::last_os_error(),
                child: None,
            });
        }

        command.kill_on_drop(true);
        command.creation_flags(CREATE_NO_WINDOW | CREATE_SUSPENDED);
        let child = command.spawn().map_err(|source| ProcessGroupSpawnError {
            source,
            child: None,
        })?;
        let mut owner = Self {
            child,
            leader_status: None,
            job,
            job_assigned: false,
        };
        #[cfg(test)]
        let spawn_failpoint = WINDOWS_SPAWN_FAILPOINT.with(std::cell::Cell::take);
        #[cfg(test)]
        if spawn_failpoint == 1 {
            return Err(ProcessGroupSpawnError {
                source: io::Error::other("injected job assignment failure"),
                child: Some(Box::new(owner)),
            });
        }
        if let Err(error) = assign_child_to_job(&mut owner.child, raw_job) {
            return Err(ProcessGroupSpawnError {
                source: error,
                child: Some(Box::new(owner)),
            });
        }
        owner.job_assigned = true;
        #[cfg(test)]
        if spawn_failpoint == 2 {
            return Err(ProcessGroupSpawnError {
                source: io::Error::other("injected suspended-thread resume failure"),
                child: Some(Box::new(owner)),
            });
        }
        if let Err(error) = resume_child_threads(&mut owner.child) {
            return Err(ProcessGroupSpawnError {
                source: error,
                child: Some(Box::new(owner)),
            });
        }
        Ok(owner)
    }

    pub(super) fn id(&self) -> Option<u32> {
        self.child.id()
    }

    pub(super) fn inner(&mut self) -> &mut Child {
        &mut self.child
    }

    pub(super) fn try_wait(&mut self) -> io::Result<Option<ExitStatus>> {
        if self.leader_status.is_none() {
            self.leader_status = self.child.try_wait()?;
        }
        let Some(status) = self.leader_status else {
            return Ok(None);
        };
        if self.group_is_empty()? {
            Ok(Some(status))
        } else {
            Ok(None)
        }
    }

    pub(super) fn start_kill(&mut self) -> io::Result<()> {
        self.terminate_group()
    }

    #[cfg(target_os = "linux")]
    fn terminate_group(&mut self) -> io::Result<()> {
        if let Some(group) = self.group.as_mut() {
            group
                .terminate()
                .map_err(|error| io::Error::other(error.to_string()))
        } else {
            terminate_numeric_group(self.pgid)
        }
    }

    #[cfg(all(unix, not(target_os = "linux")))]
    fn terminate_group(&mut self) -> io::Result<()> {
        terminate_numeric_group(self.pgid)
    }

    #[cfg(windows)]
    fn terminate_group(&mut self) -> io::Result<()> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::System::JobObjects::TerminateJobObject;

        if !self.job_assigned {
            return self.child.start_kill();
        }
        let result = unsafe { TerminateJobObject(self.job.as_raw_handle(), 1) };
        if result == 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }

    #[cfg(target_os = "linux")]
    fn group_is_empty(&mut self) -> io::Result<bool> {
        if let Some(group) = self.group.as_mut() {
            group
                .is_empty()
                .map_err(|error| io::Error::other(error.to_string()))
        } else {
            numeric_group_is_empty(self.pgid)
        }
    }

    #[cfg(all(unix, not(target_os = "linux")))]
    fn group_is_empty(&self) -> io::Result<bool> {
        numeric_group_is_empty(self.pgid)
    }

    #[cfg(windows)]
    fn group_is_empty(&self) -> io::Result<bool> {
        use std::mem::size_of;
        use std::os::windows::io::AsRawHandle;
        use std::ptr;
        use windows_sys::Win32::System::JobObjects::{
            JobObjectBasicAccountingInformation, QueryInformationJobObject,
            JOBOBJECT_BASIC_ACCOUNTING_INFORMATION,
        };

        if !self.job_assigned {
            return Ok(true);
        }
        let mut accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION::default();
        let result = unsafe {
            QueryInformationJobObject(
                self.job.as_raw_handle(),
                JobObjectBasicAccountingInformation,
                (&raw mut accounting).cast(),
                size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32,
                ptr::null_mut(),
            )
        };
        if result == 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(accounting.ActiveProcesses == 0)
        }
    }
}

#[cfg(unix)]
fn terminate_numeric_group(pgid: i32) -> io::Result<()> {
    let result = unsafe { libc::kill(-pgid, libc::SIGKILL) };
    if result == 0 {
        return Ok(());
    }
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(error)
    }
}

#[cfg(unix)]
fn numeric_group_is_empty(pgid: i32) -> io::Result<bool> {
    let result = unsafe { libc::kill(-pgid, 0) };
    if result == 0 {
        return Ok(false);
    }
    let error = io::Error::last_os_error();
    match error.raw_os_error() {
        Some(libc::ESRCH) => Ok(true),
        Some(libc::EPERM) => Ok(false),
        _ => Err(error),
    }
}

#[cfg(windows)]
fn assign_child_to_job(
    child: &mut Child,
    job: windows_sys::Win32::Foundation::HANDLE,
) -> io::Result<()> {
    use windows_sys::Win32::System::JobObjects::AssignProcessToJobObject;

    let process = child
        .raw_handle()
        .ok_or_else(|| io::Error::other("suspended child has no process handle"))?;
    if unsafe { AssignProcessToJobObject(job, process) } == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(windows)]
fn resume_child_threads(child: &mut Child) -> io::Result<()> {
    use std::mem::size_of;
    use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};

    use windows_sys::Win32::Foundation::{GetLastError, ERROR_NO_MORE_FILES, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Thread32First, Thread32Next, TH32CS_SNAPTHREAD, THREADENTRY32,
    };
    use windows_sys::Win32::System::Threading::{
        GetProcessId, OpenThread, ResumeThread, THREAD_SUSPEND_RESUME,
    };

    let process = child
        .raw_handle()
        .ok_or_else(|| io::Error::other("suspended child has no process handle"))?;
    let process_id = unsafe { GetProcessId(process) };
    if process_id == 0 {
        return Err(io::Error::last_os_error());
    }

    let raw_snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
    if raw_snapshot == INVALID_HANDLE_VALUE {
        return Err(io::Error::last_os_error());
    }
    let snapshot = unsafe { OwnedHandle::from_raw_handle(raw_snapshot) };
    let mut entry = THREADENTRY32 {
        dwSize: size_of::<THREADENTRY32>() as u32,
        ..Default::default()
    };
    let mut found = false;
    let mut available = unsafe { Thread32First(snapshot.as_raw_handle(), &mut entry) };
    loop {
        if available == 0 {
            let code = unsafe { GetLastError() };
            if code == ERROR_NO_MORE_FILES {
                break;
            }
            return Err(io::Error::from_raw_os_error(code as i32));
        }
        if entry.th32OwnerProcessID == process_id {
            let raw_thread = unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID) };
            if raw_thread.is_null() {
                return Err(io::Error::last_os_error());
            }
            let thread = unsafe { OwnedHandle::from_raw_handle(raw_thread) };
            if unsafe { ResumeThread(thread.as_raw_handle()) } == u32::MAX {
                return Err(io::Error::last_os_error());
            }
            found = true;
        }
        available = unsafe { Thread32Next(snapshot.as_raw_handle(), &mut entry) };
    }
    if found {
        Ok(())
    } else {
        Err(io::Error::other(
            "suspended child exposed no thread to resume",
        ))
    }
}

static CLEANUP_COORDINATOR: OnceLock<Result<CleanupCoordinator, String>> = OnceLock::new();
static UNRECOVERABLE_CLEANUPS: OnceLock<Mutex<Vec<CleanupRequest>>> = OnceLock::new();

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) enum ReapOutcome {
    Reaped,
    Failed(String),
}

#[derive(Clone, Debug)]
pub(super) struct ReapTicket {
    receiver: watch::Receiver<Option<ReapOutcome>>,
}

impl ReapTicket {
    pub(super) fn current(&self) -> Option<ReapOutcome> {
        self.receiver.borrow().clone()
    }

    pub(super) async fn wait(&mut self) -> ReapOutcome {
        loop {
            if let Some(outcome) = self.receiver.borrow().clone() {
                return outcome;
            }
            if self.receiver.changed().await.is_err() {
                return ReapOutcome::Failed(
                    "process owner closed without publishing a reap outcome".to_string(),
                );
            }
        }
    }

    pub(super) async fn wait_bounded(&mut self, timeout: Duration) -> Option<ReapOutcome> {
        tokio::time::timeout(timeout, self.wait()).await.ok()
    }

    pub(super) fn confirm_reaped(&self) -> Result<(), String> {
        match self.current() {
            Some(ReapOutcome::Reaped) => Ok(()),
            Some(ReapOutcome::Failed(error)) => Err(error),
            None => Err("process exited without publishing its reap outcome".to_string()),
        }
    }
}

/// Inseparable ownership of a live process group and its reap observation.
///
/// Callers can clone an observation ticket for recovery monitors, but cannot
/// construct a running process owner without retaining the canonical ticket.
pub(super) struct OwnedProcessGroup {
    owner: ProcessGroupOwner,
    ticket: ReapTicket,
}

impl OwnedProcessGroup {
    pub(super) fn new(child: ProcessGroupChild, label: &'static str) -> Self {
        let (owner, ticket) = ProcessGroupOwner::new(child, label);
        Self { owner, ticket }
    }

    pub(super) fn reap_ticket(&self) -> ReapTicket {
        self.ticket.clone()
    }

    pub(super) fn confirm_reaped(&self) -> Result<(), String> {
        self.ticket.confirm_reaped()
    }

    #[cfg(test)]
    pub(super) fn id(&self) -> Option<u32> {
        self.owner.id()
    }

    pub(super) fn inner_mut(&mut self) -> Option<&mut ProcessGroupChild> {
        self.owner.inner_mut()
    }

    pub(super) fn try_wait(&mut self) -> io::Result<Option<ExitStatus>> {
        self.owner.try_wait()
    }

    pub(super) fn start_kill(&mut self) -> io::Result<()> {
        self.owner.start_kill()
    }

    pub(super) async fn terminate_and_reap(&mut self, timeout: Duration) -> Result<(), String> {
        self.owner.terminate_and_reap(timeout).await?;
        self.confirm_reaped()
    }

    #[cfg(test)]
    pub(super) fn inject_wait_error(&mut self, error: io::Error) {
        self.owner.inject_wait_error(error);
    }

    #[cfg(test)]
    fn leader_has_exited(&self) -> bool {
        self.owner
            .child
            .as_ref()
            .and_then(|child| child.leader_status)
            .is_some()
    }
}

/// Sole owner of a backend process-group/job handle.
///
/// Releasing the Rust value never means that the process was reaped. The
/// companion ticket is completed only after `try_wait` confirms exit. A drop
/// path transfers the stable handle to the process cleanup coordinator and
/// therefore cannot silently reopen the single-task slot.
struct ProcessGroupOwner {
    child: Option<ProcessGroupChild>,
    outcome: watch::Sender<Option<ReapOutcome>>,
    label: &'static str,
    #[cfg(test)]
    injected_wait_error: Option<io::Error>,
}

impl ProcessGroupOwner {
    fn new(child: ProcessGroupChild, label: &'static str) -> (Self, ReapTicket) {
        let (outcome, receiver) = watch::channel(None);
        (
            Self {
                child: Some(child),
                outcome,
                label,
                #[cfg(test)]
                injected_wait_error: None,
            },
            ReapTicket { receiver },
        )
    }

    #[cfg(test)]
    pub(super) fn id(&self) -> Option<u32> {
        self.child.as_ref().and_then(ProcessGroupChild::id)
    }

    pub(super) fn inner_mut(&mut self) -> Option<&mut ProcessGroupChild> {
        self.child.as_mut()
    }

    pub(super) fn try_wait(&mut self) -> io::Result<Option<ExitStatus>> {
        #[cfg(test)]
        if let Some(error) = self.injected_wait_error.take() {
            return Err(error);
        }
        let result = self
            .child
            .as_mut()
            .expect("process owner is disarmed only after reap")
            .try_wait()?;
        if result.is_some() {
            self.child.take();
            self.publish(ReapOutcome::Reaped);
        }
        Ok(result)
    }

    pub(super) fn start_kill(&mut self) -> io::Result<()> {
        match self.child.as_mut() {
            Some(child) => child.start_kill(),
            None => Ok(()),
        }
    }

    #[cfg(test)]
    pub(super) fn inject_wait_error(&mut self, error: io::Error) {
        self.injected_wait_error = Some(error);
    }

    pub(super) async fn terminate_and_reap(&mut self, timeout: Duration) -> Result<(), String> {
        if self.child.is_none() {
            return Ok(());
        }
        let kill_error = self.start_kill().err();
        let deadline = Instant::now() + timeout;
        loop {
            match self.try_wait() {
                Ok(Some(_)) => return Ok(()),
                Ok(None) if Instant::now() < deadline => {
                    tokio::time::sleep(EXIT_POLL_INTERVAL).await;
                }
                Ok(None) => {
                    return Err(format!(
                        "timed out while reaping {}{}",
                        self.label,
                        format_kill_error(kill_error.as_ref())
                    ));
                }
                Err(error) => {
                    return Err(format!(
                        "unable to reap {}: {error}{}",
                        self.label,
                        format_kill_error(kill_error.as_ref())
                    ));
                }
            }
        }
    }

    fn publish(&self, outcome: ReapOutcome) {
        if self.outcome.borrow().is_none() {
            self.outcome.send_replace(Some(outcome));
        }
    }
}

impl Drop for ProcessGroupOwner {
    fn drop(&mut self) {
        let Some(child) = self.child.take() else {
            return;
        };
        submit_cleanup(CleanupRequest::new(child, self.outcome.clone(), self.label));
    }
}

struct CleanupCoordinator {
    sender: mpsc::Sender<CleanupRequest>,
    // The global coordinator owns its worker for the application lifetime.
    // Keeping the join handle makes the single background owner explicit.
    _worker: thread::JoinHandle<()>,
}

struct CleanupRequest {
    child: ProcessGroupChild,
    outcome: watch::Sender<Option<ReapOutcome>>,
    label: &'static str,
    kill_error: Option<io::Error>,
    deadline: StdInstant,
    timeout_reported: bool,
    wait_error_reported: bool,
}

impl CleanupRequest {
    fn new(
        mut child: ProcessGroupChild,
        outcome: watch::Sender<Option<ReapOutcome>>,
        label: &'static str,
    ) -> Self {
        let kill_error = request_termination(&mut child);
        Self {
            child,
            outcome,
            label,
            kill_error,
            deadline: StdInstant::now() + StartTaskSpec::TERMINATION_TIMEOUT,
            timeout_reported: false,
            wait_error_reported: false,
        }
    }

    fn poll(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(Some(_)) => {
                publish_once(&self.outcome, ReapOutcome::Reaped);
                true
            }
            Ok(None) => {
                self.report_timeout_if_due();
                false
            }
            Err(error) => {
                if !self.wait_error_reported {
                    eprintln!(
                        "unable to reap {}: {error}{}",
                        self.label,
                        format_kill_error(self.kill_error.as_ref())
                    );
                    self.wait_error_reported = true;
                }
                self.report_timeout_if_due();
                false
            }
        }
    }

    fn report_timeout_if_due(&mut self) {
        if !self.timeout_reported && StdInstant::now() >= self.deadline {
            eprintln!(
                "timed out while reaping {}{}; the cleanup coordinator retains ownership",
                self.label,
                format_kill_error(self.kill_error.as_ref())
            );
            self.timeout_reported = true;
        }
    }

    fn fail_permanently(&self, message: String) {
        eprintln!("{message}");
        publish_once(&self.outcome, ReapOutcome::Failed(message));
    }
}

fn submit_cleanup(request: CleanupRequest) {
    match cleanup_coordinator() {
        Ok(coordinator) => {
            if let Err(error) = coordinator.sender.send(request) {
                retain_unrecoverable_cleanup(
                    error.0,
                    "process cleanup coordinator stopped unexpectedly",
                );
            }
        }
        Err(error) => retain_unrecoverable_cleanup(request, &error),
    }
}

fn cleanup_coordinator() -> Result<&'static CleanupCoordinator, String> {
    match CLEANUP_COORDINATOR.get_or_init(start_cleanup_coordinator) {
        Ok(coordinator) => Ok(coordinator),
        Err(error) => Err(error.clone()),
    }
}

fn start_cleanup_coordinator() -> Result<CleanupCoordinator, String> {
    let (sender, receiver) = mpsc::channel();
    let worker = thread::Builder::new()
        .name("vp-process-cleanup".to_string())
        .spawn(move || run_cleanup_coordinator(receiver))
        .map_err(|error| format!("unable to start process cleanup coordinator: {error}"))?;
    Ok(CleanupCoordinator {
        sender,
        _worker: worker,
    })
}

fn run_cleanup_coordinator(receiver: mpsc::Receiver<CleanupRequest>) {
    let mut active = Vec::new();
    loop {
        match receiver.recv_timeout(EXIT_POLL_INTERVAL) {
            Ok(request) => active.push(request),
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) if active.is_empty() => return,
            Err(mpsc::RecvTimeoutError::Disconnected) => {}
        }
        active.extend(receiver.try_iter());

        let mut index = 0;
        while index < active.len() {
            if active[index].poll() {
                active.swap_remove(index);
            } else {
                index += 1;
            }
        }
    }
}

fn retain_unrecoverable_cleanup(request: CleanupRequest, reason: &str) {
    request.fail_permanently(format!(
        "{reason}; retaining the stable handle for {}",
        request.label
    ));
    UNRECOVERABLE_CLEANUPS
        .get_or_init(|| Mutex::new(Vec::new()))
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
        .push(request);
}

fn publish_once(sender: &watch::Sender<Option<ReapOutcome>>, outcome: ReapOutcome) {
    if sender.borrow().is_none() {
        sender.send_replace(Some(outcome));
    }
}

fn request_termination(child: &mut ProcessGroupChild) -> Option<io::Error> {
    child.start_kill().err()
}

fn format_kill_error(kill_error: Option<&io::Error>) -> String {
    kill_error
        .map(|error| format!("; termination request failed: {error}"))
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use std::process::Stdio;

    use tokio::process::Command;

    use super::*;
    use crate::tasks::test_support::assert_process_exited;

    const FIXTURE_MODE_ENV: &str = "VP_PROCESS_GROUP_TEST_MODE";
    const FIXTURE_PID_FILE_ENV: &str = "VP_PROCESS_GROUP_TEST_PID_FILE";
    const FIXTURE_TEST_NAME: &str = "tasks::subprocess::tests::process_group_child_fixture";

    #[test]
    fn process_group_child_fixture() {
        let Ok(mode) = std::env::var(FIXTURE_MODE_ENV) else {
            return;
        };
        match mode.as_str() {
            "leader" => {
                let pid_file = std::env::var_os(FIXTURE_PID_FILE_ENV).expect("fixture pid file");
                let mut descendant = std::process::Command::new(
                    std::env::current_exe().expect("current test executable"),
                );
                descendant
                    .args([
                        "--exact",
                        FIXTURE_TEST_NAME,
                        "--nocapture",
                        "--test-threads=1",
                    ])
                    .env(FIXTURE_MODE_ENV, "descendant")
                    .env_remove(FIXTURE_PID_FILE_ENV)
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null());
                #[expect(
                    clippy::zombie_processes,
                    reason = "the fixture intentionally exits its leader without waiting so the owner must retain the descendant"
                )]
                let child = descendant.spawn().expect("spawn descendant fixture");
                std::fs::write(pid_file, child.id().to_string()).expect("publish descendant pid");
            }
            "descendant" => std::thread::sleep(Duration::from_secs(60)),
            other => panic!("unknown process group fixture mode: {other}"),
        }
    }

    #[tokio::test]
    async fn leader_exit_does_not_publish_reaped_while_a_group_descendant_is_alive() {
        let fixture = tempfile::tempdir().expect("fixture directory");
        let pid_file = fixture.path().join("descendant.pid");
        let mut command = Command::new(std::env::current_exe().expect("current test executable"));
        command
            .args([
                "--exact",
                FIXTURE_TEST_NAME,
                "--nocapture",
                "--test-threads=1",
            ])
            .env(FIXTURE_MODE_ENV, "leader")
            .env(FIXTURE_PID_FILE_ENV, &pid_file)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        let child = ProcessGroupChild::spawn(&mut command).expect("spawn group leader fixture");
        let mut owner = OwnedProcessGroup::new(child, "descendant ownership fixture");
        let mut ticket = owner.reap_ticket();

        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                let observed = owner.try_wait().expect("poll process group");
                let leader_exited = owner.leader_has_exited();
                if leader_exited {
                    assert!(
                        observed.is_none(),
                        "live descendant must keep the group active"
                    );
                    break;
                }
                tokio::time::sleep(EXIT_POLL_INTERVAL).await;
            }
        })
        .await
        .expect("leader exits while descendant remains alive");
        assert_eq!(ticket.current(), None);

        let descendant_pid = tokio::time::timeout(Duration::from_secs(2), async {
            loop {
                if let Ok(value) = std::fs::read_to_string(&pid_file) {
                    break value.trim().parse::<u32>().expect("descendant pid");
                }
                tokio::time::sleep(EXIT_POLL_INTERVAL).await;
            }
        })
        .await
        .expect("descendant pid is published");

        owner
            .terminate_and_reap(Duration::from_secs(5))
            .await
            .expect("terminate and confirm the complete group");
        assert_eq!(
            ticket.wait_bounded(Duration::from_secs(1)).await,
            Some(ReapOutcome::Reaped)
        );
        assert_process_exited(descendant_pid, Duration::from_secs(3)).await;
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn post_spawn_windows_setup_failures_keep_the_child_owned_until_reaped() {
        for failpoint in [1, 2] {
            let mut command =
                Command::new(std::env::current_exe().expect("current test executable"));
            command
                .args([
                    "--exact",
                    FIXTURE_TEST_NAME,
                    "--nocapture",
                    "--test-threads=1",
                ])
                .env(FIXTURE_MODE_ENV, "descendant")
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            WINDOWS_SPAWN_FAILPOINT.with(|value| value.set(failpoint));
            let error = ProcessGroupChild::spawn(&mut command)
                .expect_err("the selected post-spawn setup step must fail");
            let (_source, child) = error.into_parts();
            let child = child.expect("post-spawn failure must return its stable child owner");
            let mut owner = OwnedProcessGroup::new(child, "post-spawn setup failure fixture");
            let mut ticket = owner.reap_ticket();

            owner
                .terminate_and_reap(Duration::from_secs(5))
                .await
                .expect("post-spawn failure child is killed and reaped");
            assert_eq!(
                ticket.wait_bounded(Duration::from_secs(1)).await,
                Some(ReapOutcome::Reaped)
            );
        }
    }
}
