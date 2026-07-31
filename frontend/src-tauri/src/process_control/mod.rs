//! Platform-agnostic process control surface used by the task runner.
//!
//! Organized as:
//! - this ``mod.rs`` — trait, error type, and task-bound controller
//! - ``windows.rs`` — Win32 ToolHelp suspend/resume implementation
//! - ``posix.rs`` — ``kill(-pgid, SIGSTOP/SIGCONT)`` implementation
//!
//! Errors keep their underlying ``io::Error`` source where applicable so that higher
//! layers (the task controller, the IPC layer) can preserve the chain
//! when forwarding to the frontend.

use std::error::Error;
use std::fmt;
use std::io;
#[cfg(target_os = "windows")]
use std::sync::Mutex;

#[cfg(not(target_os = "windows"))]
mod posix;
#[cfg(target_os = "windows")]
mod windows;

#[cfg(not(target_os = "windows"))]
use posix as imp;
#[cfg(target_os = "windows")]
use windows as imp;

/// Typed failure surface for [`ProcessController`] operations.
///
/// The dedicated enum lets the task layer distinguish "process is already
/// gone" during shutdown races from permission and OS failures.
#[derive(Debug)]
pub(crate) enum ProcessControlError {
    /// The target process / thread tree has no live members we can
    /// touch — usually because the backend already exited between the
    /// pause/resume dispatch and the controller waking up.
    NotFound,
    /// One or more threads were enumerated but every Suspend/Resume
    /// call failed (typical: the OS denied access mid-shutdown).
    NoControllableThreads,
    /// A numeric PID/TID now resolves to a different OS process/thread
    /// than the one captured when this task started.
    IdentityMismatch,
    /// Wrapping for unexpected OS errors. Keeps the original
    /// ``io::Error`` so the source chain survives downstream.
    Os(io::Error),
    /// The blocking worker that performs OS process enumeration failed.
    Worker(String),
}

impl fmt::Display for ProcessControlError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound => write!(f, "target process is no longer running"),
            Self::NoControllableThreads => {
                write!(f, "no controllable threads remain for the running task")
            }
            Self::IdentityMismatch => {
                write!(
                    f,
                    "process identity changed; refusing to control a reused PID or TID"
                )
            }
            Self::Os(error) => write!(f, "process control OS error: {error}"),
            Self::Worker(message) => write!(f, "process control worker failed: {message}"),
        }
    }
}

impl Error for ProcessControlError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Os(error) => Some(error),
            _ => None,
        }
    }
}

impl From<io::Error> for ProcessControlError {
    fn from(error: io::Error) -> Self {
        Self::Os(error)
    }
}

pub(crate) trait ProcessControl: Send + Sync {
    fn suspend(&self) -> Result<(), ProcessControlError>;
    fn resume(&self) -> Result<(), ProcessControlError>;
}

/// Process controller bound to one backend root process.
pub(crate) struct ProcessController {
    identity: imp::ProcessIdentity,
    #[cfg(target_os = "windows")]
    suspended_threads: Mutex<Option<imp::SuspendedThreads>>,
}

impl ProcessController {
    pub(crate) fn new(root_pid: u32) -> Result<Self, ProcessControlError> {
        Ok(Self {
            identity: imp::ProcessIdentity::capture(root_pid)?,
            #[cfg(target_os = "windows")]
            suspended_threads: Mutex::new(None),
        })
    }
}

impl ProcessControl for ProcessController {
    fn suspend(&self) -> Result<(), ProcessControlError> {
        #[cfg(target_os = "windows")]
        {
            let mut suspended = self.suspended_threads.lock().map_err(|_| {
                ProcessControlError::Worker("suspended-thread lock poisoned".into())
            })?;
            if suspended.is_some() {
                imp::validate_process_identity(&self.identity)?;
                return Ok(());
            }
            *suspended = Some(imp::suspend_process_tree(&self.identity)?);
        }
        #[cfg(not(target_os = "windows"))]
        imp::suspend_process_tree(&self.identity)?;
        Ok(())
    }

    fn resume(&self) -> Result<(), ProcessControlError> {
        #[cfg(target_os = "windows")]
        {
            let mut suspended = self.suspended_threads.lock().map_err(|_| {
                ProcessControlError::Worker("suspended-thread lock poisoned".into())
            })?;
            if let Some(threads) = suspended.as_mut() {
                imp::resume_process_tree(&self.identity, threads)?;
                *suspended = None;
            } else {
                imp::validate_process_identity(&self.identity)?;
            }
        }
        #[cfg(not(target_os = "windows"))]
        imp::resume_process_tree(&self.identity)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_uses_friendly_messages() {
        assert!(ProcessControlError::NotFound
            .to_string()
            .contains("no longer running"));
        assert!(ProcessControlError::NoControllableThreads
            .to_string()
            .contains("no controllable threads"));
        assert!(ProcessControlError::IdentityMismatch
            .to_string()
            .contains("identity changed"));
        let os = ProcessControlError::Os(io::Error::new(io::ErrorKind::PermissionDenied, "boom"));
        assert!(os.to_string().contains("boom"));
    }

    #[test]
    fn os_error_preserves_source_chain() {
        let inner = io::Error::new(io::ErrorKind::PermissionDenied, "denied");
        let err = ProcessControlError::Os(inner);
        assert!(err.source().is_some());
    }

    #[test]
    fn from_io_error_wraps_into_os_variant() {
        let inner = io::Error::other("nope");
        let err: ProcessControlError = inner.into();
        assert!(matches!(err, ProcessControlError::Os(_)));
    }
}
