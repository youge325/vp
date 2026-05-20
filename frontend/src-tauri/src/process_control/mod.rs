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
        #[cfg(target_os = "windows")]
        self.store_thread_cache(root_pid, threads);
        Ok(())
    }

    fn resume(&self, root_pid: u32) -> Result<(), ProcessControlError> {
        #[cfg(target_os = "windows")]
        let cached = self.take_thread_cache(root_pid);
        #[cfg(not(target_os = "windows"))]
        let cached: Option<Vec<u32>> = None;
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
        // Phase 16 — 单锁取走缓存。``HashMap::remove`` 直接返回 owned
        // ``Vec<u32>``,既完成了"读取"也完成了"释放",一次 lock 就够。
        // 之前是 lock→clone→unlock→lock→remove 的双锁结构,中间窗口允许
        // 两次 resume() 同时拿到同一份缓存(注释自圆其说是 "harmless")。
        // 用单锁后 race 直接消失,且少付一次 ``MutexGuard`` 构造开销。
        self.cached_threads
            .lock()
            .ok()
            .and_then(|mut cache| cache.remove(&root_pid))
    }
}

// Phase 4.1 — POSIX 空实现已删除。``suspend`` / ``resume`` 在 POSIX 路径上
// 不再调用 ``store_thread_cache`` / ``take_thread_cache``(通过 ``#[cfg]``
// 条件编译),因此无需保留无意义的方法。

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

    // Phase 16 — 单锁化后 take_thread_cache 必须真正"原子取走":两次
    // 调用同一 pid,只有第一次拿到 cache,第二次返回 None。之前双锁版本
    // 中间释放过 guard,理论上允许两个 take 在 remove 之前都看到 cache。
    #[cfg(target_os = "windows")]
    #[test]
    fn take_thread_cache_is_consume_once_after_phase_16() {
        let controller = DefaultProcessController::new();
        controller.store_thread_cache(1234, vec![10, 20, 30]);

        let first = controller.take_thread_cache(1234);
        let second = controller.take_thread_cache(1234);

        assert_eq!(first.as_deref(), Some(&[10u32, 20, 30][..]));
        assert!(second.is_none(), "cache must be consumed by the first take");
    }
}
