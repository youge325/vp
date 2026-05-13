use std::sync::Arc;

pub trait ProcessController: Send + Sync {
    fn suspend(&self, root_pid: u32) -> Result<(), String>;
    fn resume(&self, root_pid: u32) -> Result<(), String>;
}

#[derive(Default)]
pub struct WindowsProcessController {
    /// Cache of thread IDs collected on the last ``suspend()`` per root pid.
    ///
    /// Phase C.2.6:在 resume 时优先复用 suspend 期间扫到的 thread_ids,
    /// 避免对全系统 ToolHelp 二次枚举(系统线程数轻易过万,每次 O(N))。
    /// 由于 suspend 会让所有相关线程冻结,resume 时新建线程的可能性极低,
    /// 复用 cache 是安全的;万一 cache miss(或 cache 过期),resume 会
    /// fall back 到全扫并刷新 cache。
    ///
    /// 生命周期与单个 task 一致:[`tasks::controller::spawn_task_controller`]
    /// 每次为新任务实例化一个 ``WindowsProcessController``,任务结束后整个
    /// controller 被 drop,cache 自然回收。
    #[cfg(target_os = "windows")]
    cached_threads: std::sync::Mutex<std::collections::HashMap<u32, Vec<u32>>>,
}

impl WindowsProcessController {
    pub fn new() -> Self {
        Self::default()
    }
}

impl ProcessController for WindowsProcessController {
    fn suspend(&self, root_pid: u32) -> Result<(), String> {
        #[cfg(target_os = "windows")]
        {
            let threads = imp::set_process_tree_suspended(root_pid, true, None)?;
            if let Ok(mut cache) = self.cached_threads.lock() {
                cache.insert(root_pid, threads);
            }
            return Ok(());
        }
        #[cfg(not(target_os = "windows"))]
        {
            imp::set_process_tree_suspended(root_pid, true, None).map(|_| ())
        }
    }

    fn resume(&self, root_pid: u32) -> Result<(), String> {
        #[cfg(target_os = "windows")]
        {
            // Cache 命中:只对已知 thread_id 调 ResumeThread,免去全系统枚举
            let cached = self
                .cached_threads
                .lock()
                .ok()
                .and_then(|cache| cache.get(&root_pid).cloned());
            let _ = imp::set_process_tree_suspended(root_pid, false, cached)?;
            // Resume 后清掉缓存,避免对同一 root_pid 再次 resume 时引用过期 id
            if let Ok(mut cache) = self.cached_threads.lock() {
                cache.remove(&root_pid);
            }
            return Ok(());
        }
        #[cfg(not(target_os = "windows"))]
        {
            imp::set_process_tree_suspended(root_pid, false, None).map(|_| ())
        }
    }
}

pub fn default_controller() -> Arc<dyn ProcessController> {
    Arc::new(WindowsProcessController::new())
}

// ------------------------------------------------------------------
// Platform-specific implementation
// ------------------------------------------------------------------

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

    /// Suspend / resume a process tree.
    ///
    /// ``cached_threads`` (Phase C.2.6):
    /// - ``None`` — 全扫:用 ToolHelp 枚举所有进程和线程,过滤出 root_pid
    ///   的进程树,然后对每个线程 OpenThread + Suspend/Resume。返回的 Vec
    ///   就是这次实际操作过的 thread_ids。
    /// - ``Some(threads)`` — 快路径:跳过枚举,直接对给定的 thread_ids 调
    ///   Suspend/ResumeThread。若全部失败,自动 fall back 到全扫。
    ///
    /// Phase D.3.3 — suspend 路径在完成第一轮扫描后再扫一次,捕获在第一轮
    /// 扫描期间 spawn 出来的新孙进程线程(race 闭合)。同时 ``set_threads_suspended``
    /// 现在会在 partial failure 时 rollback,避免留下"半冻结"的进程树。
    pub fn set_process_tree_suspended(
        root_pid: u32,
        suspend: bool,
        cached_threads: Option<Vec<u32>>,
    ) -> Result<Vec<u32>, String> {
        // 优先走 cache 快路径
        if let Some(threads) = cached_threads {
            if !threads.is_empty() {
                let (touched, last_error) = set_specific_threads_suspended(&threads, suspend);
                if touched > 0 {
                    return Ok(threads);
                }
                // 全部失败:cache 过期(进程已死 / 线程已退出),退回全扫
                let _ = last_error;
            }
        }

        let pids = collect_process_tree(root_pid)?;
        let (touched_threads, mut threads) = set_threads_suspended(&pids, suspend)?;
        if touched_threads == 0 {
            return Err("No live threads were found for the running task.".to_string());
        }

        // Phase D.3.3 — only the suspend direction has a race-with-spawn
        // window. resume runs against a frozen tree, so spawning new
        // workers can't happen there; one pass is enough.
        if suspend {
            let already = threads.iter().copied().collect::<std::collections::BTreeSet<_>>();
            let pids_after = collect_process_tree(root_pid)?;
            // Second pass picks up children that spawned between
            // ToolHelp snapshot 1 and the first ``SuspendThread`` calls.
            if let Ok((_, new_threads)) = set_threads_suspended(&pids_after, suspend) {
                for tid in new_threads {
                    if !already.contains(&tid) {
                        threads.push(tid);
                    }
                }
            }
        }

        Ok(threads)
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

    /// 通过线程快照枚举所有线程,过滤出属于 pids 的线程,逐个 Suspend/Resume。
    /// 返回 ``(touched_count, thread_ids)`` — 后者用于 caller 缓存,下次
    /// resume 时跳过这一步。
    ///
    /// Phase D.3.3 — partial-failure rollback。在 ``suspend == true`` 模式下,
    /// 如果某个线程 SuspendThread 失败,先前已 suspend 的线程会被 ResumeThread
    /// 复位,避免留下半冻结的进程树。``resume`` 模式不做 rollback:目的本就是
    /// 让线程跑起来,失败也无需回滚。
    fn set_threads_suspended(
        pids: &BTreeSet<u32>,
        suspend: bool,
    ) -> Result<(usize, Vec<u32>), String> {
        let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
        if snapshot == INVALID_HANDLE_VALUE {
            return Err(last_os_error("Unable to enumerate threads"));
        }

        let mut touched_threads = 0usize;
        let mut last_error: Option<String> = None;
        let mut touched_ids: Vec<u32> = Vec::new();
        let mut entry = THREADENTRY32 {
            dwSize: size_of::<THREADENTRY32>() as u32,
            ..unsafe { std::mem::zeroed() }
        };

        let mut has_entry = unsafe { Thread32First(snapshot, &mut entry) } != 0;
        while has_entry {
            if pids.contains(&entry.th32OwnerProcessID) {
                match set_thread_suspended(entry.th32ThreadID, suspend) {
                    Ok(()) => {
                        touched_threads += 1;
                        touched_ids.push(entry.th32ThreadID);
                    }
                    Err(error) => {
                        last_error = Some(error);
                        if suspend {
                            // Phase D.3.3 — rollback to avoid a half-frozen
                            // process tree. Best-effort: ResumeThread errors
                            // here would be reported in the parent error.
                            for &tid in &touched_ids {
                                let _ = set_thread_suspended(tid, false);
                            }
                            unsafe {
                                let _ = CloseHandle(snapshot);
                            }
                            return Err(last_error.unwrap_or_else(|| {
                                "Suspend rollback triggered on unknown failure.".to_string()
                            }));
                        }
                    }
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

        Ok((touched_threads, touched_ids))
    }

    /// 缓存命中时的快路径:对给定 thread_ids 直接 Suspend/ResumeThread,
    /// 不枚举线程快照。返回 ``(touched_count, last_error)``。
    fn set_specific_threads_suspended(
        thread_ids: &[u32],
        suspend: bool,
    ) -> (usize, Option<String>) {
        let mut touched = 0usize;
        let mut last_error = None;
        for &tid in thread_ids {
            match set_thread_suspended(tid, suspend) {
                Ok(()) => touched += 1,
                Err(error) => last_error = Some(error),
            }
        }
        (touched, last_error)
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
    /// POSIX 版本不需要 thread enumeration:``kill(-pgid, SIGSTOP/SIGCONT)``
    /// 对整个进程组一次完成。``cached_threads`` 在 POSIX 上未使用,签名保持
    /// 一致只是为了 cross-platform call site 不分叉。
    pub fn set_process_tree_suspended(
        root_pid: u32,
        suspend: bool,
        _cached_threads: Option<Vec<u32>>,
    ) -> Result<Vec<u32>, String> {
        unsafe {
            let pgid = libc::getpgid(root_pid as i32);
            if pgid < 0 {
                return Err("Unable to get process group id".to_string());
            }
            let signal = if suspend { libc::SIGSTOP } else { libc::SIGCONT };
            let result = libc::kill(-pgid, signal);
            if result < 0 {
                return Err(format!(
                    "kill failed: {}",
                    std::io::Error::last_os_error()
                ));
            }
            Ok(Vec::new())
        }
    }
}
