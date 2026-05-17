//! Platform-agnostic process control surface used by the task runner.
//!
//! Phase 5a split the previous single-file ``process_control.rs`` into:
//! - this ``mod.rs`` — trait, error type, controller struct, factory
//! - ``windows.rs`` — Win32 ToolHelp suspend/resume implementation
//! - ``posix.rs`` — ``kill(-pgid, SIGSTOP/SIGCONT)`` implementation
//!
//! The trait now returns a typed [`ProcessControlError`] instead of the
//! free-form ``Result<(), String>`` it inherited from Phase C. Errors keep
//! their underlying ``io::Error`` source where applicable so that higher
//! layers (the task controller, the IPC layer) can preserve the chain
//! when forwarding to the frontend.

use std::error::Error;
use std::fmt;
use std::io;
use std::sync::Arc;

#[cfg(target_os = "windows")]
mod windows;
#[cfg(not(target_os = "windows"))]
mod posix;

#[cfg(target_os = "windows")]
use windows as imp;
#[cfg(not(target_os = "windows"))]
use posix as imp;

/// Typed failure surface for [`ProcessController`] operations.
///
/// Previously every controller call returned ``Result<(), String>``,
/// which forced callers to either re-parse the message or treat all
/// failures identically. With a dedicated enum the controller and the
/// task layer can distinguish "process is already gone" (which is often
/// benign during cancellation races) from a real permission / OS issue.
#[derive(Debug)]
pub enum ProcessControlError {
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
}

impl fmt::Display for ProcessControlError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound => write!(f, "target process is no longer running"),
            Self::NoControllableThreads => {
                write!(f, "no controllable threads remain for the running task")
            }
            Self::Os(error) => write!(f, "process control OS error: {error}"),
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

pub trait ProcessController: Send + Sync {
    fn suspend(&self, root_pid: u32) -> Result<(), ProcessControlError>;
    fn resume(&self, root_pid: u32) -> Result<(), ProcessControlError>;
}

/// Default controller exposed to the rest of the crate.
///
/// Both Windows and POSIX paths reuse the same struct because the
/// thread cache is only populated on Windows; on POSIX
/// ``cached_threads`` stays empty and the field is gated behind
/// ``#[cfg(target_os = "windows")]`` anyway.
#[derive(Default)]
pub struct DefaultProcessController {
    /// Cache of thread IDs collected on the last ``suspend()`` per root pid.
    ///
    /// Phase C.2.6 — populated by [`imp::set_process_tree_suspended`] when
    /// running on Windows so that ``resume()`` can skip a second full
    /// ToolHelp enumeration. Stays empty on POSIX (``kill(-pgid)`` reaches
    /// every member of the process group in one syscall).
    ///
    /// Lifetime mirrors a single task: ``tasks::controller::spawn_task_controller``
    /// constructs one per task and drops it on completion, so the cache
    /// is naturally reclaimed at task boundaries.
    #[cfg(target_os = "windows")]
    cached_threads: std::sync::Mutex<std::collections::HashMap<u32, Vec<u32>>>,
}

impl DefaultProcessController {
    pub fn new() -> Self {
        Self::default()
    }
}

impl ProcessController for DefaultProcessController {
    fn suspend(&self, root_pid: u32) -> Result<(), ProcessControlError> {
        let threads = imp::set_process_tree_suspended(root_pid, true, None)?;
        self.store_thread_cache(root_pid, threads);
        Ok(())
    }

    fn resume(&self, root_pid: u32) -> Result<(), ProcessControlError> {
        let cached = self.take_thread_cache(root_pid);
        let _ = imp::set_process_tree_suspended(root_pid, false, cached)?;
        Ok(())
    }
}

#[cfg(target_os = "windows")]
impl DefaultProcessController {
    fn store_thread_cache(&self, root_pid: u32, threads: Vec<u32>) {
        if let Ok(mut cache) = self.cached_threads.lock() {
            cache.insert(root_pid, threads);
        }
    }

    fn take_thread_cache(&self, root_pid: u32) -> Option<Vec<u32>> {
        // Cache hit: only re-touch the threads we suspended last time
        // instead of paying for another system-wide ToolHelp scan.
        // The lookup-then-remove sequence keeps the lock window short
        // (drop the guard between the two), at the cost of a tiny
        // race where two ``resume()`` calls for the same pid could
        // both grab the cached vec; that's harmless because the
        // second ``ResumeThread`` is a no-op for already-running threads.
        let cached = self
            .cached_threads
            .lock()
            .ok()
            .and_then(|cache| cache.get(&root_pid).cloned());
        if let Ok(mut cache) = self.cached_threads.lock() {
            cache.remove(&root_pid);
        }
        cached
    }
}

#[cfg(not(target_os = "windows"))]
impl DefaultProcessController {
    fn store_thread_cache(&self, _root_pid: u32, _threads: Vec<u32>) {
        // POSIX path doesn't enumerate threads — ``kill(-pgid, signal)``
        // covers every group member in one syscall, so there's nothing
        // worth caching.
    }

    fn take_thread_cache(&self, _root_pid: u32) -> Option<Vec<u32>> {
        None
    }
}

pub fn default_controller() -> Arc<dyn ProcessController> {
    Arc::new(DefaultProcessController::new())
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
}
