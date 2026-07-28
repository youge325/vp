//! POSIX implementation of process-tree suspend/resume.
//!
//! Unlike Windows we don't need ToolHelp-style thread enumeration —
//! ``kill(-pgid, SIGSTOP/SIGCONT)`` covers every member of the process
//! group in a single syscall.

use std::io;

use super::ProcessControlError;

pub(crate) fn suspend_process_tree(root_pid: u32) -> Result<(), ProcessControlError> {
    signal_process_tree(root_pid, libc::SIGSTOP)
}

pub(crate) fn resume_process_tree(root_pid: u32) -> Result<(), ProcessControlError> {
    signal_process_tree(root_pid, libc::SIGCONT)
}

fn signal_process_tree(root_pid: u32, signal: i32) -> Result<(), ProcessControlError> {
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
        let result = libc::kill(-pgid, signal);
        if result < 0 {
            let error = io::Error::last_os_error();
            return if error.raw_os_error() == Some(libc::ESRCH) {
                Err(ProcessControlError::NotFound)
            } else {
                Err(ProcessControlError::Os(error))
            };
        }
        Ok(())
    }
}
