use std::time::Duration;

pub(super) async fn assert_process_exited(pid: u32, timeout: Duration) {
    tokio::time::timeout(timeout, async {
        while process_is_running(pid) {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .expect("subprocess must be killed and reaped within the bounded policy");
}

#[cfg(windows)]
fn process_is_running(pid: u32) -> bool {
    use windows_sys::Win32::Foundation::{CloseHandle, WAIT_TIMEOUT};
    use windows_sys::Win32::System::Threading::{
        OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE,
    };

    // SAFETY: `OpenProcess` returns an owned handle for the supplied PID; the
    // handle is closed exactly once before returning.
    unsafe {
        let handle = OpenProcess(PROCESS_SYNCHRONIZE, 0, pid);
        if handle.is_null() {
            return false;
        }
        let result = WaitForSingleObject(handle, 0);
        let _ = CloseHandle(handle);
        result == WAIT_TIMEOUT
    }
}

#[cfg(unix)]
fn process_is_running(pid: u32) -> bool {
    // SAFETY: signal zero checks process existence without delivering a
    // signal.
    let result = unsafe { libc::kill(pid as libc::pid_t, 0) };
    result == 0 || std::io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}
