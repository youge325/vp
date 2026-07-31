//! POSIX process-group control with stable root-process identity validation.
//!
//! Linux retains a pidfd and `/proc/<pid>/stat` start time. macOS records
//! `proc_bsdinfo` start time. The captured PGID is signalled only after the
//! current PID has been proven to still identify the same process.

use std::io;

use super::ProcessControlError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ProcessIdentityKey {
    pid: i32,
    pgid: i32,
    started_at: u128,
}

pub(crate) struct ProcessIdentity {
    key: ProcessIdentityKey,
    #[cfg(target_os = "linux")]
    pidfd: std::os::fd::OwnedFd,
}

impl ProcessIdentity {
    pub(crate) fn capture(root_pid: u32) -> Result<Self, ProcessControlError> {
        let pid = i32::try_from(root_pid).map_err(|_| ProcessControlError::NotFound)?;
        let key = read_process_identity(pid)?;
        if key.pid != pid || key.pgid != pid {
            return Err(ProcessControlError::IdentityMismatch);
        }
        #[cfg(target_os = "linux")]
        let pidfd = open_pidfd(pid)?;
        Ok(Self {
            key,
            #[cfg(target_os = "linux")]
            pidfd,
        })
    }
}

pub(crate) fn suspend_process_tree(identity: &ProcessIdentity) -> Result<(), ProcessControlError> {
    signal_process_tree(identity, libc::SIGSTOP)
}

pub(crate) fn resume_process_tree(identity: &ProcessIdentity) -> Result<(), ProcessControlError> {
    signal_process_tree(identity, libc::SIGCONT)
}

fn signal_process_tree(identity: &ProcessIdentity, signal: i32) -> Result<(), ProcessControlError> {
    validate_process_identity(identity)?;
    let result = unsafe { libc::kill(-identity.key.pgid, signal) };
    if result < 0 {
        return Err(classify_os_error(io::Error::last_os_error()));
    }
    Ok(())
}

fn validate_process_identity(identity: &ProcessIdentity) -> Result<(), ProcessControlError> {
    #[cfg(target_os = "linux")]
    ensure_pidfd_live(&identity.pidfd)?;
    let observed = read_process_identity(identity.key.pid)?;
    if identity_matches(identity.key, observed) {
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
fn read_process_identity(pid: i32) -> Result<ProcessIdentityKey, ProcessControlError> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat"))
        .map_err(|error| classify_os_error(error))?;
    parse_linux_stat(&stat)
}

#[cfg(target_os = "linux")]
fn parse_linux_stat(stat: &str) -> Result<ProcessIdentityKey, ProcessControlError> {
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
    let pgid = fields
        .get(2)
        .and_then(|value| value.parse::<i32>().ok())
        .ok_or_else(|| {
            ProcessControlError::Os(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid process group in /proc stat",
            ))
        })?;
    let started_at = fields
        .get(19)
        .and_then(|value| value.parse::<u128>().ok())
        .ok_or_else(|| {
            ProcessControlError::Os(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid start time in /proc stat",
            ))
        })?;
    Ok(ProcessIdentityKey {
        pid,
        pgid,
        started_at,
    })
}

#[cfg(target_os = "linux")]
fn open_pidfd(pid: i32) -> Result<std::os::fd::OwnedFd, ProcessControlError> {
    use std::os::fd::FromRawFd;

    let raw = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) as i32 };
    if raw < 0 {
        return Err(classify_os_error(io::Error::last_os_error()));
    }
    Ok(unsafe { std::os::fd::OwnedFd::from_raw_fd(raw) })
}

#[cfg(target_os = "linux")]
fn ensure_pidfd_live(pidfd: &std::os::fd::OwnedFd) -> Result<(), ProcessControlError> {
    use std::os::fd::AsRawFd;

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

#[cfg(target_os = "macos")]
fn read_process_identity(pid: i32) -> Result<ProcessIdentityKey, ProcessControlError> {
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
        let error = io::Error::last_os_error();
        return Err(classify_os_error(error));
    }
    Ok(ProcessIdentityKey {
        pid: info.pbi_pid as i32,
        pgid: info.pbi_pgid as i32,
        started_at: (u128::from(info.pbi_start_tvsec) * 1_000_000)
            + u128::from(info.pbi_start_tvusec),
    })
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
fn read_process_identity(_pid: i32) -> Result<ProcessIdentityKey, ProcessControlError> {
    Err(ProcessControlError::Worker(
        "stable process identity is unavailable on this POSIX platform".to_string(),
    ))
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
    fn parses_linux_stat_with_spaces_and_parentheses_in_command() {
        let stat =
            "123 (worker (gpu) pool) S 1 123 123 0 -1 0 1 2 3 4 5 6 7 8 9 10 11 12 98765 0 0";
        let identity = parse_linux_stat(stat).expect("valid stat");

        assert_eq!(
            identity,
            ProcessIdentityKey {
                pid: 123,
                pgid: 123,
                started_at: 98765,
            }
        );
    }
}
