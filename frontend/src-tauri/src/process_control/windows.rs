//! Windows ToolHelp-based suspend/resume of an entire process tree.
//!
//! Split out of the legacy ``process_control.rs`` mod in Phase 5a so the
//! mod root only sees the trait + factory; the platform impl details
//! live here behind the same ``set_process_tree_suspended`` entry point
//! that ``DefaultProcessController`` calls into.

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

use super::ProcessControlError;

/// Suspend / resume a process tree.
///
/// ``cached_threads`` (Phase C.2.6):
/// - ``None`` — full scan: enumerate every process and thread via ToolHelp,
///   filter to ``root_pid``'s descendant tree, and Suspend/Resume each
///   thread individually. The returned ``Vec`` is the set of thread IDs
///   actually touched so the caller can cache it for next time.
/// - ``Some(threads)`` — fast path: skip enumeration and call
///   Suspend/ResumeThread on the cached IDs directly. If all of them
///   fail (cache stale because threads died), automatically fall back
///   to a full scan.
///
/// Phase D.3.3 — the suspend direction makes a second pass after the
/// first round of ``SuspendThread`` calls to catch grandchildren that
/// spawned between the snapshot and the first freeze. ``resume`` runs
/// against an already-frozen tree, so one pass is sufficient and the
/// rollback bookkeeping is unnecessary there.
///
/// Phase 12 — the second pass previously called ``SuspendThread`` on
/// *every* thread under ``root_pid``'s tree, including the ones the
/// first pass had already frozen. That bumped their suspend-count from
/// 1 to 2, and the matching ``ResumeThread`` (which only walks the
/// cached thread IDs once) could only knock it back down to 1, leaving
/// the task frozen forever. Now the second pass receives an explicit
/// exclude-set of already-touched thread IDs and short-circuits before
/// calling ``SuspendThread`` on them, so each tid has its suspend-count
/// raised at most once per ``set_process_tree_suspended`` invocation.
pub fn set_process_tree_suspended(
    root_pid: u32,
    suspend: bool,
    cached_threads: Option<Vec<u32>>,
) -> Result<Vec<u32>, ProcessControlError> {
    if let Some(threads) = cached_threads {
        if !threads.is_empty() {
            let (touched, last_error) = set_specific_threads_suspended(&threads, suspend);
            if touched > 0 {
                return Ok(threads);
            }
            // Every cached thread is gone: drop to a full scan to find
            // the new (or remaining) workers.
            let _ = last_error;
        }
    }

    let pids = collect_process_tree(root_pid)?;
    let (touched_threads, mut threads) = set_threads_suspended(&pids, suspend, None)?;
    if touched_threads == 0 {
        return Err(ProcessControlError::NotFound);
    }

    if suspend {
        let already = threads.iter().copied().collect::<BTreeSet<_>>();
        let pids_after = collect_process_tree(root_pid)?;
        // Phase 12 — pass ``already`` as the exclude-set so threads we
        // already froze in the first pass are NOT re-suspended (which
        // would push their suspend-count to 2 and trap the task on the
        // subsequent ``ResumeThread`` that only knocks it down by 1).
        if let Ok((_, new_threads)) = set_threads_suspended(&pids_after, suspend, Some(&already)) {
            for tid in new_threads {
                if !already.contains(&tid) {
                    threads.push(tid);
                }
            }
        }
    }

    Ok(threads)
}

fn collect_process_tree(root_pid: u32) -> Result<BTreeSet<u32>, ProcessControlError> {
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
    if snapshot == INVALID_HANDLE_VALUE {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
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

/// Enumerate every thread on the system, filter to the ones owned by
/// ``pids``, and Suspend/Resume each. Returns ``(touched_count, thread_ids)``
/// so the caller can cache the IDs for the next ``resume()`` call.
///
/// Phase D.3.3 — on suspend, a partial failure triggers a rollback that
/// Resume's every thread we already froze, preventing a half-frozen
/// process tree. Resume mode never rolls back: the goal there is to
/// let threads run, so a partial success is still better than nothing.
///
/// Phase 12 — ``exclude_tids`` lets the caller skip Suspend/ResumeThread
/// for thread IDs whose state was already manipulated in an earlier call
/// (specifically, the D.3.3 second pass passes the first pass's touched
/// IDs so they don't get a second SuspendThread that would lift their
/// suspend-count to 2). Excluded tids are NOT returned in ``touched_ids``
/// either, since the cache already covers them.
fn set_threads_suspended(
    pids: &BTreeSet<u32>,
    suspend: bool,
    exclude_tids: Option<&BTreeSet<u32>>,
) -> Result<(usize, Vec<u32>), ProcessControlError> {
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
    if snapshot == INVALID_HANDLE_VALUE {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }

    let mut touched_threads = 0usize;
    let mut last_error: Option<ProcessControlError> = None;
    let mut touched_ids: Vec<u32> = Vec::new();
    let mut entry = THREADENTRY32 {
        dwSize: size_of::<THREADENTRY32>() as u32,
        ..unsafe { std::mem::zeroed() }
    };

    let mut has_entry = unsafe { Thread32First(snapshot, &mut entry) } != 0;
    while has_entry {
        if thread_should_be_touched(
            pids,
            exclude_tids,
            entry.th32OwnerProcessID,
            entry.th32ThreadID,
        ) {
            match set_thread_suspended(entry.th32ThreadID, suspend) {
                Ok(()) => {
                    touched_threads += 1;
                    touched_ids.push(entry.th32ThreadID);
                }
                Err(error) => {
                    last_error = Some(error);
                    if suspend {
                        for &tid in &touched_ids {
                            let _ = set_thread_suspended(tid, false);
                        }
                        unsafe {
                            let _ = CloseHandle(snapshot);
                        }
                        return Err(
                            last_error.unwrap_or(ProcessControlError::NoControllableThreads)
                        );
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
        return Err(last_error.unwrap_or(ProcessControlError::NoControllableThreads));
    }

    Ok((touched_threads, touched_ids))
}

fn set_specific_threads_suspended(
    thread_ids: &[u32],
    suspend: bool,
) -> (usize, Option<ProcessControlError>) {
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

fn set_thread_suspended(thread_id: u32, suspend: bool) -> Result<(), ProcessControlError> {
    let thread = unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, thread_id) };
    if thread.is_null() {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
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
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }

    Ok(())
}

/// Pure-decision helper extracted from ``set_threads_suspended`` so the
/// Phase 12 second-pass exclude logic can be unit-tested without a real
/// process tree.
///
/// Returns ``true`` iff the thread (``thread_id`` owned by ``owner_pid``)
/// should have ``SuspendThread`` / ``ResumeThread`` called on it during
/// the current pass.
fn thread_should_be_touched(
    pids: &BTreeSet<u32>,
    exclude_tids: Option<&BTreeSet<u32>>,
    owner_pid: u32,
    thread_id: u32,
) -> bool {
    if !pids.contains(&owner_pid) {
        return false;
    }
    match exclude_tids {
        Some(set) => !set.contains(&thread_id),
        None => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pid_set(values: &[u32]) -> BTreeSet<u32> {
        values.iter().copied().collect()
    }

    #[test]
    fn touches_thread_when_owner_pid_matches_and_no_exclude_set() {
        let pids = pid_set(&[100, 200]);
        assert!(thread_should_be_touched(&pids, None, 100, 7777));
    }

    #[test]
    fn skips_thread_whose_owner_pid_is_outside_the_tree() {
        let pids = pid_set(&[100, 200]);
        assert!(!thread_should_be_touched(&pids, None, 999, 1234));
    }

    #[test]
    fn second_pass_skips_threads_already_suspended_in_first_pass() {
        // Phase 12 — this is the regression guard against the D.3.3
        // second-pass double-suspend bug: a tid in the exclude set must
        // NOT be touched, otherwise its SuspendThread call would push
        // its suspend-count to 2 and the subsequent ResumeThread (which
        // only runs once over the cached IDs) leaves the task frozen.
        let pids = pid_set(&[100]);
        let already_touched = pid_set(&[7777, 8888]);
        assert!(!thread_should_be_touched(
            &pids,
            Some(&already_touched),
            100,
            7777,
        ));
        assert!(!thread_should_be_touched(
            &pids,
            Some(&already_touched),
            100,
            8888,
        ));
    }

    #[test]
    fn second_pass_still_touches_brand_new_grandchild_threads() {
        // After the first SuspendThread pass, a grandchild may spawn a
        // new thread that isn't in the exclude set. Catching it is the
        // entire reason the second pass exists in the first place; the
        // Phase 12 fix must NOT throw the baby out with the bathwater.
        let pids = pid_set(&[100]);
        let already_touched = pid_set(&[7777]);
        assert!(thread_should_be_touched(
            &pids,
            Some(&already_touched),
            100,
            9999,
        ));
    }

    #[test]
    fn empty_pid_set_skips_every_thread() {
        // Defensive: if collect_process_tree somehow returns an empty
        // set (process already gone between the two snapshots), we just
        // don't touch anything — same outcome as the natural for-loop
        // having no matches.
        let pids = pid_set(&[]);
        assert!(!thread_should_be_touched(&pids, None, 100, 7777));
    }
}
