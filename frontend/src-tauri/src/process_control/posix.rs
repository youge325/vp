//! POSIX implementation of process-tree suspend/resume.
//!
//! Unlike Windows we don't need ToolHelp-style thread enumeration —
//! ``kill(-pgid, SIGSTOP/SIGCONT)`` covers every member of the process
//! group in a single syscall. The ``cached_threads`` parameter is
//! accepted only to keep the cross-platform call-site signature
//! identical with the Windows impl; the value is ignored.

use std::io;

use super::ProcessControlError;

pub fn set_process_tree_suspended(
    root_pid: u32,
    suspend: bool,
    _cached_threads: Option<Vec<u32>>,
) -> Result<Vec<u32>, ProcessControlError> {
    unsafe {
        let pgid = libc::getpgid(root_pid as i32);
        if pgid < 0 {
            // ESRCH = process is gone; treat as NotFound so the
            // controller can swallow it during cancellation races
            // instead of bubbling up a generic OS error.
            let err = io::Error::last_os_error();
            return if err.raw_os_error() == Some(libc::ESRCH) {
                Err(ProcessControlError::NotFound)
            } else {
                Err(ProcessControlError::Os(err))
            };
        }
        let signal = if suspend {
            libc::SIGSTOP
        } else {
            libc::SIGCONT
        };
        let result = libc::kill(-pgid, signal);
        if result < 0 {
            return Err(ProcessControlError::Os(io::Error::last_os_error()));
        }
        Ok(Vec::new())
    }
}
