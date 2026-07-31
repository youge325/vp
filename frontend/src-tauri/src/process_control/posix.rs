//! Stable process control for non-Windows platforms.
//!
//! Linux discovers a process tree to a fixed point, opens a pidfd for every
//! member, and signals only those retained handles. macOS intentionally
//! rejects pause/resume because its process APIs do not provide an equivalent
//! stable signalling handle; cancellation remains available through the task
//! supervisor.

use std::io;

#[cfg(target_os = "linux")]
use std::collections::{BTreeMap, BTreeSet};
#[cfg(target_os = "linux")]
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};

use super::ProcessControlError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ProcessIdentityKey {
    pid: i32,
    pgid: i32,
    started_at: u128,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ProcessSnapshot {
    key: ProcessIdentityKey,
    #[cfg(target_os = "linux")]
    parent_pid: i32,
}

pub(super) struct ProcessIdentity {
    key: ProcessIdentityKey,
    #[cfg(target_os = "linux")]
    pidfd: OwnedFd,
}

impl ProcessIdentity {
    pub(super) fn capture(root_pid: u32) -> Result<Self, ProcessControlError> {
        let pid = i32::try_from(root_pid).map_err(|_| ProcessControlError::NotFound)?;
        let snapshot = read_process_snapshot(pid)?;
        if snapshot.key.pid != pid {
            return Err(ProcessControlError::IdentityMismatch);
        }
        #[cfg(target_os = "linux")]
        if snapshot.key.pgid != pid {
            return Err(ProcessControlError::IdentityMismatch);
        }
        #[cfg(target_os = "linux")]
        let pidfd = open_pidfd(pid)?;
        let identity = Self {
            key: snapshot.key,
            #[cfg(target_os = "linux")]
            pidfd,
        };
        validate_process_identity(&identity)?;
        Ok(identity)
    }
}

#[cfg(target_os = "linux")]
struct StableProcess {
    snapshot: ProcessSnapshot,
    pidfd: OwnedFd,
}

/// Stable ownership set used by the subprocess adapter for cancellation and
/// full-group exit confirmation. Discovery is repeated to a fixed point and
/// every candidate is pinned with a pidfd before it can be signalled.
#[cfg(target_os = "linux")]
pub(crate) struct StableProcessGroup {
    root: ProcessIdentityKey,
    processes: BTreeMap<i32, StableProcess>,
}

#[cfg(target_os = "linux")]
impl StableProcessGroup {
    pub(crate) fn capture(root_pid: u32) -> Result<Self, ProcessControlError> {
        let pid = i32::try_from(root_pid).map_err(|_| ProcessControlError::NotFound)?;
        let root = read_process_snapshot(pid)?;
        if root.key.pid != pid || root.key.pgid != pid {
            return Err(ProcessControlError::IdentityMismatch);
        }
        let process = StableProcess::capture(root)?;
        let mut group = Self {
            root: root.key,
            processes: BTreeMap::from([(pid, process)]),
        };
        group.refresh()?;
        Ok(group)
    }

    pub(crate) fn is_empty(&mut self) -> Result<bool, ProcessControlError> {
        self.refresh()?;
        self.processes
            .retain(|_, process| match ensure_pidfd_live(&process.pidfd) {
                Ok(()) => true,
                Err(ProcessControlError::NotFound) => false,
                Err(_) => true,
            });
        for process in self.processes.values() {
            ensure_pidfd_live(&process.pidfd)?;
        }
        Ok(self.processes.is_empty())
    }

    pub(crate) fn terminate(&mut self) -> Result<(), ProcessControlError> {
        const MAX_FIXED_POINT_PASSES: usize = 64;

        for _ in 0..MAX_FIXED_POINT_PASSES {
            self.refresh()?;
            let mut live = false;
            for process in self.processes.values() {
                match signal_pidfd(&process.pidfd, libc::SIGKILL) {
                    Ok(()) => live = true,
                    Err(ProcessControlError::NotFound) => {}
                    Err(error) => return Err(error),
                }
            }
            if !live {
                return Ok(());
            }
            let before = self.processes.len();
            self.refresh()?;
            if self.processes.len() == before {
                return Ok(());
            }
        }
        Err(ProcessControlError::Worker(
            "Linux process group did not reach a stable termination fixed point".to_string(),
        ))
    }

    fn refresh(&mut self) -> Result<(), ProcessControlError> {
        const MAX_FIXED_POINT_PASSES: usize = 64;

        for _ in 0..MAX_FIXED_POINT_PASSES {
            self.processes
                .retain(|_, process| match ensure_pidfd_live(&process.pidfd) {
                    Ok(()) => true,
                    Err(ProcessControlError::NotFound) => false,
                    Err(_) => true,
                });
            let table = read_process_table()?;
            let candidates = collect_process_tree_candidates(self.root, &table);
            for pid in candidates {
                let Some(expected) = table.get(&pid).copied() else {
                    continue;
                };
                if let Some(held) = self.processes.get(&pid) {
                    if held.snapshot != expected {
                        return Err(ProcessControlError::IdentityMismatch);
                    }
                    continue;
                }
                match StableProcess::capture(expected) {
                    Ok(process) => {
                        self.processes.insert(pid, process);
                    }
                    Err(ProcessControlError::NotFound) => {}
                    Err(error) => return Err(error),
                }
            }

            let confirmed = read_process_table()?;
            let confirmed_candidates = collect_process_tree_candidates(self.root, &confirmed);
            if fixed_point_is_stable(&confirmed_candidates, &confirmed, |pid| {
                self.processes.get(&pid).map(|held| held.snapshot)
            }) {
                return Ok(());
            }
        }
        Err(ProcessControlError::Worker(
            "Linux process group discovery did not reach a stable fixed point".to_string(),
        ))
    }
}

#[cfg(target_os = "linux")]
impl StableProcess {
    fn capture(expected: ProcessSnapshot) -> Result<Self, ProcessControlError> {
        let pidfd = open_pidfd(expected.key.pid)?;
        ensure_pidfd_live(&pidfd)?;
        let observed = read_process_snapshot(expected.key.pid)?;
        if observed != expected {
            return Err(ProcessControlError::IdentityMismatch);
        }
        Ok(Self {
            snapshot: expected,
            pidfd,
        })
    }
}

#[cfg(target_os = "linux")]
pub(super) struct SuspendedProcesses {
    processes: BTreeMap<i32, StableProcess>,
}

#[cfg(target_os = "linux")]
pub(super) fn suspend_process_tree(
    identity: &ProcessIdentity,
) -> Result<SuspendedProcesses, ProcessControlError> {
    const MAX_FIXED_POINT_PASSES: usize = 64;

    validate_process_identity(identity)?;
    let mut suspended = BTreeMap::new();
    for _ in 0..MAX_FIXED_POINT_PASSES {
        let table = match read_process_table() {
            Ok(table) => table,
            Err(error) => {
                return Err(failure_after_linux_rollback(error, &mut suspended));
            }
        };
        if let Err(error) = validate_root_snapshot(identity, &table) {
            return Err(failure_after_linux_rollback(error, &mut suspended));
        }
        let candidates = collect_process_tree_candidates(identity.key, &table);

        let ordered_candidates = std::iter::once(identity.key.pid).chain(
            candidates
                .into_iter()
                .filter(|pid| *pid != identity.key.pid),
        );
        for pid in ordered_candidates {
            if let Some(held_snapshot) = suspended.get(&pid).map(|held| held.snapshot) {
                let Some(observed) = table.get(&pid) else {
                    return Err(failure_after_linux_rollback(
                        ProcessControlError::IdentityMismatch,
                        &mut suspended,
                    ));
                };
                if held_snapshot != *observed {
                    let primary = ProcessControlError::IdentityMismatch;
                    return Err(failure_after_linux_rollback(primary, &mut suspended));
                }
                continue;
            }
            let Some(expected) = table.get(&pid).copied() else {
                return Err(failure_after_linux_rollback(
                    ProcessControlError::IdentityMismatch,
                    &mut suspended,
                ));
            };
            let process = match StableProcess::capture(expected) {
                Ok(process) => process,
                Err(ProcessControlError::NotFound) if pid != identity.key.pid => continue,
                Err(error) => {
                    return Err(failure_after_linux_rollback(error, &mut suspended));
                }
            };
            match signal_pidfd(&process.pidfd, libc::SIGSTOP) {
                Ok(()) => {
                    suspended.insert(pid, process);
                }
                Err(ProcessControlError::NotFound) if pid != identity.key.pid => {}
                Err(error) => {
                    return Err(failure_after_linux_rollback(error, &mut suspended));
                }
            }
        }

        let confirmed = match read_process_table() {
            Ok(table) => table,
            Err(error) => {
                return Err(failure_after_linux_rollback(error, &mut suspended));
            }
        };
        if let Err(error) = validate_root_snapshot(identity, &confirmed) {
            return Err(failure_after_linux_rollback(error, &mut suspended));
        }
        let confirmed_candidates = collect_process_tree_candidates(identity.key, &confirmed);
        let stable = fixed_point_is_stable(&confirmed_candidates, &confirmed, |pid| {
            suspended.get(&pid).map(|held| held.snapshot)
        });
        if stable {
            if let Err(error) = validate_process_identity(identity) {
                return Err(failure_after_linux_rollback(error, &mut suspended));
            }
            return Ok(SuspendedProcesses {
                processes: suspended,
            });
        }
    }

    Err(failure_after_linux_rollback(
        ProcessControlError::Worker(
            "Linux process tree did not reach a stable fixed point".to_string(),
        ),
        &mut suspended,
    ))
}

#[cfg(target_os = "linux")]
pub(super) fn resume_process_tree(
    _identity: &ProcessIdentity,
    suspended: &mut SuspendedProcesses,
) -> Result<(), ProcessControlError> {
    let mut failures = Vec::new();
    suspended.processes.retain(
        |pid, process| match signal_pidfd(&process.pidfd, libc::SIGCONT) {
            Ok(()) | Err(ProcessControlError::NotFound) => false,
            Err(error) => {
                failures.push(format!("pid {pid}: {error}"));
                true
            }
        },
    );
    if failures.is_empty() {
        Ok(())
    } else {
        Err(ProcessControlError::StateUnknown(format!(
            "failed to resume the retained pidfd set: {}",
            failures.join("; ")
        )))
    }
}

#[cfg(not(target_os = "linux"))]
pub(super) fn suspend_process_tree(_identity: &ProcessIdentity) -> Result<(), ProcessControlError> {
    Err(ProcessControlError::Unsupported)
}

#[cfg(not(target_os = "linux"))]
pub(super) fn resume_process_tree(_identity: &ProcessIdentity) -> Result<(), ProcessControlError> {
    Err(ProcessControlError::Unsupported)
}

pub(super) fn validate_process_identity(
    identity: &ProcessIdentity,
) -> Result<(), ProcessControlError> {
    #[cfg(target_os = "linux")]
    ensure_pidfd_live(&identity.pidfd)?;
    let observed = read_process_snapshot(identity.key.pid)?;
    if identity_matches(identity.key, observed.key) {
        Ok(())
    } else {
        Err(ProcessControlError::IdentityMismatch)
    }
}

fn identity_matches(expected: ProcessIdentityKey, observed: ProcessIdentityKey) -> bool {
    expected == observed
}

fn classify_os_error(error: io::Error) -> ProcessControlError {
    if error.raw_os_error() == Some(libc::ESRCH) || error.kind() == io::ErrorKind::NotFound {
        ProcessControlError::NotFound
    } else {
        ProcessControlError::Os(error)
    }
}

#[cfg(target_os = "linux")]
fn validate_root_snapshot(
    identity: &ProcessIdentity,
    table: &BTreeMap<i32, ProcessSnapshot>,
) -> Result<(), ProcessControlError> {
    let observed = table
        .get(&identity.key.pid)
        .ok_or(ProcessControlError::NotFound)?;
    if identity_matches(identity.key, observed.key) {
        Ok(())
    } else {
        Err(ProcessControlError::IdentityMismatch)
    }
}

#[cfg(target_os = "linux")]
fn read_process_table() -> Result<BTreeMap<i32, ProcessSnapshot>, ProcessControlError> {
    let mut table = BTreeMap::new();
    for entry in std::fs::read_dir("/proc").map_err(ProcessControlError::Os)? {
        let entry = entry.map_err(ProcessControlError::Os)?;
        let Some(pid) = entry
            .file_name()
            .to_str()
            .and_then(|name| name.parse::<i32>().ok())
        else {
            continue;
        };
        match read_process_snapshot(pid) {
            Ok(snapshot) => {
                table.insert(pid, snapshot);
            }
            Err(ProcessControlError::NotFound) => {}
            Err(error) => return Err(error),
        }
    }
    Ok(table)
}

#[cfg(target_os = "linux")]
fn collect_process_tree_candidates(
    root: ProcessIdentityKey,
    table: &BTreeMap<i32, ProcessSnapshot>,
) -> BTreeSet<i32> {
    let parents = table
        .iter()
        .map(|(pid, snapshot)| (*pid, snapshot.parent_pid))
        .collect::<BTreeMap<_, _>>();
    let mut pids = BTreeSet::from([root.pid]);
    let mut changed = true;
    while changed {
        changed = false;
        for (pid, parent_pid) in &parents {
            if pids.contains(parent_pid) && pids.insert(*pid) {
                changed = true;
            }
        }
    }
    for (pid, snapshot) in table {
        if snapshot.key.pgid == root.pgid {
            pids.insert(*pid);
        }
    }
    pids
}

#[cfg(target_os = "linux")]
fn fixed_point_is_stable(
    candidates: &BTreeSet<i32>,
    confirmed: &BTreeMap<i32, ProcessSnapshot>,
    mut retained_snapshot: impl FnMut(i32) -> Option<ProcessSnapshot>,
) -> bool {
    candidates
        .iter()
        .all(|pid| retained_snapshot(*pid).is_some_and(|held| confirmed.get(pid) == Some(&held)))
}

#[cfg(target_os = "linux")]
fn read_process_snapshot(pid: i32) -> Result<ProcessSnapshot, ProcessControlError> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).map_err(classify_os_error)?;
    parse_linux_stat(&stat)
}

#[cfg(target_os = "linux")]
fn parse_linux_stat(stat: &str) -> Result<ProcessSnapshot, ProcessControlError> {
    let command_end = stat.rfind(')').ok_or_else(|| {
        ProcessControlError::Os(io::Error::new(
            io::ErrorKind::InvalidData,
            "missing command terminator in /proc stat",
        ))
    })?;
    let pid = stat[..command_end]
        .split_once('(')
        .and_then(|(pid, _)| pid.trim().parse::<i32>().ok())
        .ok_or_else(|| {
            ProcessControlError::Os(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid PID in /proc stat",
            ))
        })?;
    let fields = stat[command_end + 1..]
        .split_whitespace()
        .collect::<Vec<_>>();
    let parse_field = |index: usize, name: &str| -> Result<i32, ProcessControlError> {
        fields
            .get(index)
            .and_then(|value| value.parse::<i32>().ok())
            .ok_or_else(|| {
                ProcessControlError::Os(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("invalid {name} in /proc stat"),
                ))
            })
    };
    let parent_pid = parse_field(1, "parent PID")?;
    let pgid = parse_field(2, "process group")?;
    let started_at = fields
        .get(19)
        .and_then(|value| value.parse::<u128>().ok())
        .ok_or_else(|| {
            ProcessControlError::Os(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid start time in /proc stat",
            ))
        })?;
    Ok(ProcessSnapshot {
        key: ProcessIdentityKey {
            pid,
            pgid,
            started_at,
        },
        parent_pid,
    })
}

#[cfg(target_os = "linux")]
fn open_pidfd(pid: i32) -> Result<OwnedFd, ProcessControlError> {
    let raw = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) as i32 };
    if raw < 0 {
        return Err(classify_os_error(io::Error::last_os_error()));
    }
    Ok(unsafe { OwnedFd::from_raw_fd(raw) })
}

#[cfg(target_os = "linux")]
fn ensure_pidfd_live(pidfd: &OwnedFd) -> Result<(), ProcessControlError> {
    let mut descriptor = libc::pollfd {
        fd: pidfd.as_raw_fd(),
        events: libc::POLLIN,
        revents: 0,
    };
    match unsafe { libc::poll(&mut descriptor, 1, 0) } {
        0 => Ok(()),
        result if result > 0 => Err(ProcessControlError::NotFound),
        _ => Err(ProcessControlError::Os(io::Error::last_os_error())),
    }
}

#[cfg(target_os = "linux")]
fn signal_pidfd(pidfd: &OwnedFd, signal: i32) -> Result<(), ProcessControlError> {
    let result = unsafe {
        libc::syscall(
            libc::SYS_pidfd_send_signal,
            pidfd.as_raw_fd(),
            signal,
            std::ptr::null::<libc::siginfo_t>(),
            0,
        )
    };
    if result < 0 {
        Err(classify_os_error(io::Error::last_os_error()))
    } else {
        Ok(())
    }
}

#[cfg(target_os = "linux")]
fn rollback_linux_processes(
    processes: &mut BTreeMap<i32, StableProcess>,
) -> Result<(), ProcessControlError> {
    let mut failures = Vec::new();
    for (pid, process) in std::mem::take(processes) {
        match signal_pidfd(&process.pidfd, libc::SIGCONT) {
            Ok(()) | Err(ProcessControlError::NotFound) => {}
            Err(error) => failures.push(format!("pid {pid}: {error}")),
        }
    }
    if failures.is_empty() {
        Ok(())
    } else {
        Err(ProcessControlError::StateUnknown(format!(
            "failed to resume pidfds during rollback: {}",
            failures.join("; ")
        )))
    }
}

#[cfg(target_os = "linux")]
fn failure_after_linux_rollback(
    primary: ProcessControlError,
    processes: &mut BTreeMap<i32, StableProcess>,
) -> ProcessControlError {
    match rollback_linux_processes(processes) {
        Ok(()) => primary,
        Err(rollback) => ProcessControlError::StateUnknown(format!(
            "primary failure: {primary}; rollback failure: {rollback}"
        )),
    }
}

#[cfg(target_os = "macos")]
fn read_process_snapshot(pid: i32) -> Result<ProcessSnapshot, ProcessControlError> {
    let mut info = unsafe { std::mem::zeroed::<libc::proc_bsdinfo>() };
    let expected_size = std::mem::size_of::<libc::proc_bsdinfo>();
    let received = unsafe {
        libc::proc_pidinfo(
            pid,
            libc::PROC_PIDTBSDINFO,
            0,
            (&mut info as *mut libc::proc_bsdinfo).cast(),
            expected_size as i32,
        )
    };
    if received != expected_size as i32 {
        return Err(classify_os_error(io::Error::last_os_error()));
    }
    Ok(ProcessSnapshot {
        key: ProcessIdentityKey {
            pid: info.pbi_pid as i32,
            pgid: info.pbi_pgid as i32,
            started_at: (u128::from(info.pbi_start_tvsec) * 1_000_000)
                + u128::from(info.pbi_start_tvusec),
        },
    })
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
fn read_process_snapshot(_pid: i32) -> Result<ProcessSnapshot, ProcessControlError> {
    Err(ProcessControlError::Unsupported)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pid_reuse_is_rejected_when_start_time_changes() {
        let expected = ProcessIdentityKey {
            pid: 42,
            pgid: 42,
            started_at: 100,
        };
        let reused = ProcessIdentityKey {
            started_at: 101,
            ..expected
        };

        assert!(!identity_matches(expected, reused));
    }

    #[test]
    fn process_group_change_is_rejected() {
        let expected = ProcessIdentityKey {
            pid: 42,
            pgid: 42,
            started_at: 100,
        };
        let moved = ProcessIdentityKey {
            pgid: 84,
            ..expected
        };

        assert!(!identity_matches(expected, moved));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn parses_linux_stat_with_parent_group_and_start_time() {
        let stat =
            "123 (worker (gpu) pool) S 7 123 123 0 -1 0 1 2 3 4 5 6 7 8 9 10 11 12 98765 0 0";
        let snapshot = parse_linux_stat(stat).expect("valid stat");

        assert_eq!(
            snapshot,
            ProcessSnapshot {
                key: ProcessIdentityKey {
                    pid: 123,
                    pgid: 123,
                    started_at: 98765,
                },
                parent_pid: 7,
            }
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn fixed_point_candidates_include_descendants_and_same_group_members() {
        let root = ProcessIdentityKey {
            pid: 10,
            pgid: 10,
            started_at: 1,
        };
        let snapshot = |pid, parent_pid, pgid| ProcessSnapshot {
            key: ProcessIdentityKey {
                pid,
                pgid,
                started_at: pid as u128,
            },
            parent_pid,
        };
        let table = BTreeMap::from([
            (10, snapshot(10, 1, 10)),
            (11, snapshot(11, 10, 11)),
            (12, snapshot(12, 11, 12)),
            (13, snapshot(13, 1, 10)),
            (20, snapshot(20, 1, 20)),
        ]);

        assert_eq!(
            collect_process_tree_candidates(root, &table),
            BTreeSet::from([10, 11, 12, 13])
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn fixed_point_rejects_a_reused_pid_identity() {
        let original = ProcessSnapshot {
            key: ProcessIdentityKey {
                pid: 10,
                pgid: 10,
                started_at: 100,
            },
            parent_pid: 1,
        };
        let reused = ProcessSnapshot {
            key: ProcessIdentityKey {
                started_at: 101,
                ..original.key
            },
            ..original
        };
        let candidates = BTreeSet::from([10]);
        let confirmed = BTreeMap::from([(10, reused)]);

        assert!(!fixed_point_is_stable(&candidates, &confirmed, |pid| (pid
            == 10)
            .then_some(original)));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn macos_pause_and_resume_are_explicitly_unsupported() {
        let identity = ProcessIdentity {
            key: ProcessIdentityKey {
                pid: 42,
                pgid: 42,
                started_at: 1,
            },
        };
        assert!(matches!(
            suspend_process_tree(&identity),
            Err(ProcessControlError::Unsupported)
        ));
        assert!(matches!(
            resume_process_tree(&identity),
            Err(ProcessControlError::Unsupported)
        ));
    }
}
