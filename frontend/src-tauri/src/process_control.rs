#[cfg(target_os = "windows")]
mod imp {
    use std::collections::BTreeSet;
    use std::io;
    use std::mem::size_of;

    use windows_sys::Win32::Foundation::{CloseHandle, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, Thread32First, Thread32Next,
        PROCESSENTRY32W, TH32CS_SNAPPROCESS, TH32CS_SNAPTHREAD, THREADENTRY32,
    };
    use windows_sys::Win32::System::Threading::{
        OpenThread, ResumeThread, SuspendThread, THREAD_SUSPEND_RESUME,
    };

    pub fn suspend_process_tree(root_pid: u32) -> Result<(), String> {
        set_process_tree_suspended(root_pid, true)
    }

    pub fn resume_process_tree(root_pid: u32) -> Result<(), String> {
        set_process_tree_suspended(root_pid, false)
    }

    fn set_process_tree_suspended(root_pid: u32, suspend: bool) -> Result<(), String> {
        let pids = collect_process_tree(root_pid)?;
        let touched_threads = set_threads_suspended(&pids, suspend)?;
        if touched_threads == 0 {
            return Err("No live threads were found for the running task.".to_string());
        }
        Ok(())
    }

    fn collect_process_tree(root_pid: u32) -> Result<BTreeSet<u32>, String> {
        let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
        if snapshot == INVALID_HANDLE_VALUE {
            return Err(last_os_error("Unable to enumerate processes"));
        }

        let mut entries = Vec::new();
        let mut entry = PROCESSENTRY32W {
            dwSize: size_of::<PROCESSENTRY32W>() as u32,
            ..unsafe { std::mem::zeroed() }
        };

        let mut has_entry = unsafe { Process32FirstW(snapshot, &mut entry) } != 0;
        while has_entry {
            entries.push((entry.th32ProcessID, entry.th32ParentProcessID));
            has_entry = unsafe { Process32NextW(snapshot, &mut entry) } != 0;
        }

        unsafe {
            let _ = CloseHandle(snapshot);
        }

        let mut pids = BTreeSet::from([root_pid]);
        let mut changed = true;
        while changed {
            changed = false;
            for (pid, parent_pid) in &entries {
                if pids.contains(parent_pid) && pids.insert(*pid) {
                    changed = true;
                }
            }
        }

        Ok(pids)
    }

    fn set_threads_suspended(pids: &BTreeSet<u32>, suspend: bool) -> Result<usize, String> {
        let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
        if snapshot == INVALID_HANDLE_VALUE {
            return Err(last_os_error("Unable to enumerate threads"));
        }

        let mut touched_threads = 0usize;
        let mut last_error: Option<String> = None;
        let mut entry = THREADENTRY32 {
            dwSize: size_of::<THREADENTRY32>() as u32,
            ..unsafe { std::mem::zeroed() }
        };

        let mut has_entry = unsafe { Thread32First(snapshot, &mut entry) } != 0;
        while has_entry {
            if pids.contains(&entry.th32OwnerProcessID) {
                match set_thread_suspended(entry.th32ThreadID, suspend) {
                    Ok(()) => touched_threads += 1,
                    Err(error) => last_error = Some(error),
                }
            }
            has_entry = unsafe { Thread32Next(snapshot, &mut entry) } != 0;
        }

        unsafe {
            let _ = CloseHandle(snapshot);
        }

        if touched_threads == 0 {
            return Err(
                last_error.unwrap_or_else(|| "No task threads could be controlled.".to_string())
            );
        }

        Ok(touched_threads)
    }

    fn set_thread_suspended(thread_id: u32, suspend: bool) -> Result<(), String> {
        let thread = unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, thread_id) };
        if thread.is_null() {
            return Err(last_os_error("Unable to open task thread"));
        }

        let result = if suspend {
            unsafe { SuspendThread(thread) }
        } else {
            unsafe { ResumeThread(thread) }
        };

        unsafe {
            let _ = CloseHandle(thread);
        }

        if result == u32::MAX {
            return Err(last_os_error("Unable to update task thread state"));
        }

        Ok(())
    }

    fn last_os_error(prefix: &str) -> String {
        format!("{prefix}: {}", io::Error::last_os_error())
    }
}

#[cfg(not(target_os = "windows"))]
mod imp {
    pub fn suspend_process_tree(_root_pid: u32) -> Result<(), String> {
        Err("Task pause is only supported on Windows.".to_string())
    }

    pub fn resume_process_tree(_root_pid: u32) -> Result<(), String> {
        Err("Task resume is only supported on Windows.".to_string())
    }
}

pub use imp::{resume_process_tree, suspend_process_tree};
