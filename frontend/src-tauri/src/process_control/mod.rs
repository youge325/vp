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
    root_pid: u32,
    #[cfg(target_os = "windows")]
    cached_threads: std::sync::Mutex<Option<Vec<u32>>>,
}

impl ProcessController {
    pub(crate) fn new(root_pid: u32) -> Self {
        Self {
            root_pid,
            #[cfg(target_os = "windows")]
            cached_threads: std::sync::Mutex::new(None),
        }
    }
}

impl ProcessControl for ProcessController {
    fn suspend(&self) -> Result<(), ProcessControlError> {
        #[cfg(target_os = "windows")]
        {
            let threads = imp::suspend_process_tree(self.root_pid)?;
            if let Ok(mut cache) = self.cached_threads.lock() {
                *cache = Some(threads);
            }
        }
        #[cfg(not(target_os = "windows"))]
        imp::suspend_process_tree(self.root_pid)?;
        Ok(())
    }

    fn resume(&self) -> Result<(), ProcessControlError> {
        #[cfg(target_os = "windows")]
        {
            let cached = self
                .cached_threads
                .lock()
                .ok()
                .and_then(|mut cache| cache.take());
            imp::resume_process_tree(self.root_pid, cached)?;
        }
        #[cfg(not(target_os = "windows"))]
        imp::resume_process_tree(self.root_pid)?;
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

    #[cfg(target_os = "windows")]
    #[test]
    fn thread_cache_is_task_local_and_consumed_once() {
        let controller = ProcessController::new(1234);
        *controller.cached_threads.lock().unwrap() = Some(vec![10, 20, 30]);
        let first = controller.cached_threads.lock().unwrap().take();
        let second = controller.cached_threads.lock().unwrap().take();

        assert_eq!(first.as_deref(), Some(&[10u32, 20, 30][..]));
        assert!(second.is_none(), "cache must be consumed by the first take");
    }
}
