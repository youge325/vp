//! Windows process-tree control bound to stable process and thread handles.
//!
//! ToolHelp snapshots only discover candidates. A numeric PID/TID is never
//! trusted as the control target: the root process is held open for the task
//! lifetime, every operation revalidates its creation time, and suspended
//! threads remain owned by handle until they are resumed.

use std::collections::{BTreeMap, BTreeSet};
use std::io;
use std::mem::size_of;
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};

use windows_sys::Win32::Foundation::{
    GetLastError, ERROR_NO_MORE_FILES, FILETIME, HANDLE, INVALID_HANDLE_VALUE, WAIT_FAILED,
    WAIT_OBJECT_0, WAIT_TIMEOUT,
};
use windows_sys::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, Thread32First, Thread32Next,
    PROCESSENTRY32W, TH32CS_SNAPPROCESS, TH32CS_SNAPTHREAD, THREADENTRY32,
};
use windows_sys::Win32::System::Threading::{
    GetProcessId, GetProcessIdOfThread, GetProcessTimes, GetThreadId, GetThreadTimes, OpenProcess,
    OpenThread, ResumeThread, SuspendThread, WaitForSingleObject,
    PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SYNCHRONIZE, THREAD_QUERY_LIMITED_INFORMATION,
    THREAD_SUSPEND_RESUME, THREAD_SYNCHRONIZE,
};

use super::ProcessControlError;

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct ProcessIdentityKey {
    pid: u32,
    created_at: u64,
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct ThreadIdentityKey {
    tid: u32,
    owner: ProcessIdentityKey,
    created_at: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ThreadHandleIdentity {
    tid: u32,
    owner_pid: u32,
    created_at: u64,
}

struct StableProcess {
    key: ProcessIdentityKey,
    handle: OwnedHandle,
}

impl StableProcess {
    fn capture(pid: u32) -> Result<Self, ProcessControlError> {
        let handle = open_process(pid)?;
        let key = read_process_identity(&handle)?;
        if key.pid != pid {
            return Err(ProcessControlError::IdentityMismatch);
        }
        ensure_handle_is_live(&handle)?;
        Ok(Self { key, handle })
    }
}

struct ProcessTree {
    processes: BTreeMap<u32, StableProcess>,
}

impl ProcessTree {
    fn validate(&self) -> Result<(), ProcessControlError> {
        for process in self.processes.values() {
            validate_stable_process(process)?;
        }
        Ok(())
    }
}

pub(crate) struct ProcessIdentity {
    key: ProcessIdentityKey,
    handle: OwnedHandle,
}

impl ProcessIdentity {
    pub(crate) fn capture(root_pid: u32) -> Result<Self, ProcessControlError> {
        let process = StableProcess::capture(root_pid)?;
        Ok(Self {
            key: process.key,
            handle: process.handle,
        })
    }
}

struct SuspendedThread {
    key: ThreadIdentityKey,
    handle: OwnedHandle,
}

pub(crate) struct SuspendedThreads {
    threads: Vec<SuspendedThread>,
}

/// Suspend the stable root process tree. A second pass catches descendants
/// created during the first snapshot, while exact creation-time identities
/// prevent a recycled TID from being mistaken for an already-suspended thread.
pub(crate) fn suspend_process_tree(
    identity: &ProcessIdentity,
) -> Result<SuspendedThreads, ProcessControlError> {
    let pids = collect_process_tree(identity)?;
    let mut threads = set_threads_suspended(&pids, None)?;

    let already = threads
        .iter()
        .map(|thread| thread.key)
        .collect::<BTreeSet<_>>();
    let pids_after = match collect_process_tree(identity) {
        Ok(pids) => pids,
        Err(error) => {
            rollback_suspended_threads(&mut threads);
            return Err(error);
        }
    };
    match set_threads_suspended(&pids_after, Some(&already)) {
        Ok(mut new_threads) => threads.append(&mut new_threads),
        Err(error) => {
            rollback_suspended_threads(&mut threads);
            return Err(error);
        }
    }

    if let Err(error) = validate_process_identity(identity) {
        rollback_suspended_threads(&mut threads);
        return Err(error);
    }
    Ok(SuspendedThreads { threads })
}

/// Resume only the exact thread handles retained by the matching suspend.
///
/// Successful or exited threads are removed from the cache immediately. If a
/// live thread fails to resume its handle remains cached, so a retry cannot
/// decrement the suspend count of threads that were already resumed.
pub(crate) fn resume_process_tree(
    identity: &ProcessIdentity,
    suspended: &mut SuspendedThreads,
) -> Result<(), ProcessControlError> {
    validate_process_identity(identity)?;
    let mut first_error = None;
    suspended
        .threads
        .retain(|thread| match set_open_thread_suspended(thread, false) {
            Ok(()) => false,
            Err(ProcessControlError::NotFound) => false,
            Err(error) => {
                if first_error.is_none() {
                    first_error = Some(error);
                }
                true
            }
        });

    if suspended.threads.is_empty() {
        Ok(())
    } else {
        Err(first_error.unwrap_or(ProcessControlError::NoControllableThreads))
    }
}

pub(crate) fn validate_process_identity(
    expected: &ProcessIdentity,
) -> Result<(), ProcessControlError> {
    validate_stable_process_parts(expected.key, &expected.handle)
}

fn validate_stable_process(expected: &StableProcess) -> Result<(), ProcessControlError> {
    validate_stable_process_parts(expected.key, &expected.handle)
}

fn validate_stable_process_parts(
    expected: ProcessIdentityKey,
    held_handle: &OwnedHandle,
) -> Result<(), ProcessControlError> {
    let observed_handle = match open_process(expected.pid) {
        Ok(handle) => handle,
        Err(ProcessControlError::Os(error))
            if error.kind() == io::ErrorKind::NotFound
                || error.raw_os_error() == Some(87)
                || error.raw_os_error() == Some(1168) =>
        {
            return Err(ProcessControlError::NotFound);
        }
        Err(error) => return Err(error),
    };
    let observed = read_process_identity(&observed_handle)?;
    if !process_identity_matches(expected, observed) {
        return Err(ProcessControlError::IdentityMismatch);
    }

    let held = read_process_identity(held_handle)?;
    if !process_identity_matches(expected, held) {
        return Err(ProcessControlError::IdentityMismatch);
    }
    ensure_handle_is_live(held_handle)
}

fn process_identity_matches(expected: ProcessIdentityKey, observed: ProcessIdentityKey) -> bool {
    expected == observed
}

fn thread_identity_matches(expected: ThreadIdentityKey, observed: ThreadHandleIdentity) -> bool {
    expected.tid == observed.tid
        && expected.owner.pid == observed.owner_pid
        && expected.created_at == observed.created_at
}

fn thread_owner_binding_matches(
    expected: ProcessIdentityKey,
    observed: ProcessIdentityKey,
    thread_owner_pid: u32,
) -> bool {
    process_identity_matches(expected, observed) && thread_owner_pid == expected.pid
}

fn open_process(pid: u32) -> Result<OwnedHandle, ProcessControlError> {
    let raw = unsafe {
        OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE,
            0,
            pid,
        )
    };
    owned_handle(raw)
}

fn current_process_identity(pid: u32) -> Result<ProcessIdentityKey, ProcessControlError> {
    let handle = open_process(pid)?;
    ensure_handle_is_live(&handle)?;
    read_process_identity(&handle)
}

fn open_thread(
    tid: u32,
    expected_owner: &StableProcess,
) -> Result<SuspendedThread, ProcessControlError> {
    validate_stable_process(expected_owner)?;
    let raw = unsafe {
        OpenThread(
            THREAD_SUSPEND_RESUME | THREAD_QUERY_LIMITED_INFORMATION | THREAD_SYNCHRONIZE,
            0,
            tid,
        )
    };
    let handle = owned_handle(raw)?;
    let observed_thread = read_thread_identity(&handle)?;
    let observed_owner = current_process_identity(expected_owner.key.pid)?;
    if !thread_owner_binding_matches(
        expected_owner.key,
        observed_owner,
        observed_thread.owner_pid,
    ) {
        return Err(ProcessControlError::IdentityMismatch);
    }
    validate_stable_process(expected_owner)?;
    let key = ThreadIdentityKey {
        tid,
        owner: expected_owner.key,
        created_at: observed_thread.created_at,
    };
    if !thread_identity_matches(key, observed_thread) {
        return Err(ProcessControlError::IdentityMismatch);
    }
    Ok(SuspendedThread { key, handle })
}

fn owned_handle(raw: HANDLE) -> Result<OwnedHandle, ProcessControlError> {
    if raw.is_null() || raw == INVALID_HANDLE_VALUE {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    Ok(unsafe { OwnedHandle::from_raw_handle(raw.cast()) })
}

fn raw_handle(handle: &OwnedHandle) -> HANDLE {
    handle.as_raw_handle().cast()
}

fn read_process_identity(handle: &OwnedHandle) -> Result<ProcessIdentityKey, ProcessControlError> {
    let raw = raw_handle(handle);
    let pid = unsafe { GetProcessId(raw) };
    if pid == 0 {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    Ok(ProcessIdentityKey {
        pid,
        created_at: creation_time(raw, GetProcessTimes)?,
    })
}

fn read_thread_identity(handle: &OwnedHandle) -> Result<ThreadHandleIdentity, ProcessControlError> {
    let raw = raw_handle(handle);
    let tid = unsafe { GetThreadId(raw) };
    if tid == 0 {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    let owner_pid = unsafe { GetProcessIdOfThread(raw) };
    if owner_pid == 0 {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    Ok(ThreadHandleIdentity {
        tid,
        owner_pid,
        created_at: creation_time(raw, GetThreadTimes)?,
    })
}

fn creation_time(
    handle: HANDLE,
    get_times: unsafe extern "system" fn(
        HANDLE,
        *mut FILETIME,
        *mut FILETIME,
        *mut FILETIME,
        *mut FILETIME,
    ) -> i32,
) -> Result<u64, ProcessControlError> {
    let mut creation = FILETIME::default();
    let mut exit = FILETIME::default();
    let mut kernel = FILETIME::default();
    let mut user = FILETIME::default();
    if unsafe { get_times(handle, &mut creation, &mut exit, &mut kernel, &mut user) } == 0 {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    Ok((u64::from(creation.dwHighDateTime) << 32) | u64::from(creation.dwLowDateTime))
}

fn ensure_handle_is_live(handle: &OwnedHandle) -> Result<(), ProcessControlError> {
    match unsafe { WaitForSingleObject(raw_handle(handle), 0) } {
        WAIT_TIMEOUT => Ok(()),
        WAIT_OBJECT_0 => Err(ProcessControlError::NotFound),
        WAIT_FAILED => Err(ProcessControlError::Os(io::Error::last_os_error())),
        _ => Err(ProcessControlError::Os(io::Error::other(
            "unexpected process wait result",
        ))),
    }
}

fn snapshot_process_parents() -> Result<BTreeMap<u32, u32>, ProcessControlError> {
    let snapshot = SnapshotHandle::processes()?;
    let mut entries = BTreeMap::new();
    let mut entry = PROCESSENTRY32W {
        dwSize: size_of::<PROCESSENTRY32W>() as u32,
        ..unsafe { std::mem::zeroed() }
    };

    let mut has_entry = snapshot_result(unsafe { Process32FirstW(snapshot.raw(), &mut entry) })?;
    while has_entry {
        entries.insert(entry.th32ProcessID, entry.th32ParentProcessID);
        has_entry = snapshot_result(unsafe { Process32NextW(snapshot.raw(), &mut entry) })?;
    }
    Ok(entries)
}

fn collect_process_tree(identity: &ProcessIdentity) -> Result<ProcessTree, ProcessControlError> {
    validate_process_identity(identity)?;
    let initial_parents = snapshot_process_parents()?;
    if !initial_parents.contains_key(&identity.key.pid) {
        return Err(ProcessControlError::NotFound);
    }

    let pids = collect_descendant_pids(identity.key.pid, &initial_parents);
    let mut processes = BTreeMap::new();
    for pid in &pids {
        processes.insert(*pid, StableProcess::capture(*pid)?);
    }

    let confirmed_parents = snapshot_process_parents()?;
    for pid in &pids {
        if initial_parents.get(pid) != confirmed_parents.get(pid) {
            return Err(ProcessControlError::IdentityMismatch);
        }
    }
    let tree = ProcessTree { processes };
    tree.validate()?;
    validate_process_identity(identity)?;
    let captured_root = tree
        .processes
        .get(&identity.key.pid)
        .ok_or(ProcessControlError::NotFound)?;
    if !process_identity_matches(identity.key, captured_root.key) {
        return Err(ProcessControlError::IdentityMismatch);
    }

    for (pid, process) in &tree.processes {
        if *pid == identity.key.pid {
            continue;
        }
        let parent_pid = confirmed_parents
            .get(pid)
            .ok_or(ProcessControlError::IdentityMismatch)?;
        let parent = tree
            .processes
            .get(parent_pid)
            .ok_or(ProcessControlError::IdentityMismatch)?;
        if !valid_parent_child_identity(parent.key, process.key) {
            return Err(ProcessControlError::IdentityMismatch);
        }
    }
    Ok(tree)
}

fn collect_descendant_pids(root_pid: u32, parents: &BTreeMap<u32, u32>) -> BTreeSet<u32> {
    let mut pids = BTreeSet::from([root_pid]);
    let mut changed = true;
    while changed {
        changed = false;
        for (pid, parent_pid) in parents {
            if pids.contains(parent_pid) && pids.insert(*pid) {
                changed = true;
            }
        }
    }
    pids
}

fn valid_parent_child_identity(parent: ProcessIdentityKey, child: ProcessIdentityKey) -> bool {
    parent.pid != child.pid && child.created_at >= parent.created_at
}

fn set_threads_suspended(
    tree: &ProcessTree,
    exclude: Option<&BTreeSet<ThreadIdentityKey>>,
) -> Result<Vec<SuspendedThread>, ProcessControlError> {
    tree.validate()?;
    let snapshot = SnapshotHandle::threads()?;
    let mut touched = Vec::new();
    let mut entry = THREADENTRY32 {
        dwSize: size_of::<THREADENTRY32>() as u32,
        ..unsafe { std::mem::zeroed() }
    };

    let mut has_entry = snapshot_result(unsafe { Thread32First(snapshot.raw(), &mut entry) })?;
    while has_entry {
        if let Some(owner) = tree.processes.get(&entry.th32OwnerProcessID) {
            match open_thread(entry.th32ThreadID, owner) {
                Ok(thread) if exclude.is_some_and(|keys| keys.contains(&thread.key)) => {}
                Ok(thread) => match set_open_thread_suspended(&thread, true) {
                    Ok(()) => touched.push(thread),
                    Err(error) => {
                        rollback_suspended_threads(&mut touched);
                        return Err(error);
                    }
                },
                Err(error) => {
                    rollback_suspended_threads(&mut touched);
                    return Err(error);
                }
            }
        }
        has_entry = match snapshot_result(unsafe { Thread32Next(snapshot.raw(), &mut entry) }) {
            Ok(has_entry) => has_entry,
            Err(error) => {
                rollback_suspended_threads(&mut touched);
                return Err(error);
            }
        };
    }

    if let Err(error) = tree.validate() {
        rollback_suspended_threads(&mut touched);
        return Err(error);
    }
    if touched.is_empty() && exclude.is_none() {
        return Err(ProcessControlError::NoControllableThreads);
    }
    Ok(touched)
}

fn set_open_thread_suspended(
    thread: &SuspendedThread,
    suspend: bool,
) -> Result<(), ProcessControlError> {
    let observed = read_thread_identity(&thread.handle)?;
    if !thread_identity_matches(thread.key, observed) {
        return Err(ProcessControlError::IdentityMismatch);
    }
    if !suspend && ensure_handle_is_live(&thread.handle).is_err() {
        return Err(ProcessControlError::NotFound);
    }
    let result = if suspend {
        unsafe { SuspendThread(raw_handle(&thread.handle)) }
    } else {
        unsafe { ResumeThread(raw_handle(&thread.handle)) }
    };
    if result == u32::MAX {
        return Err(ProcessControlError::Os(io::Error::last_os_error()));
    }
    Ok(())
}

fn rollback_suspended_threads(threads: &mut Vec<SuspendedThread>) {
    for thread in threads.drain(..) {
        let _ = set_open_thread_suspended(&thread, false);
    }
}

fn snapshot_result(result: i32) -> Result<bool, ProcessControlError> {
    if result != 0 {
        return Ok(true);
    }
    classify_snapshot_error(unsafe { GetLastError() })
}

fn classify_snapshot_error(error_code: u32) -> Result<bool, ProcessControlError> {
    if error_code == ERROR_NO_MORE_FILES {
        Ok(false)
    } else {
        Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            error_code as i32,
        )))
    }
}

struct SnapshotHandle(OwnedHandle);

impl SnapshotHandle {
    fn processes() -> Result<Self, ProcessControlError> {
        Self::capture(TH32CS_SNAPPROCESS)
    }

    fn threads() -> Result<Self, ProcessControlError> {
        Self::capture(TH32CS_SNAPTHREAD)
    }

    fn capture(flags: u32) -> Result<Self, ProcessControlError> {
        let raw = unsafe { CreateToolhelp32Snapshot(flags, 0) };
        Ok(Self(owned_handle(raw)?))
    }

    fn raw(&self) -> HANDLE {
        raw_handle(&self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pid_reuse_is_rejected_when_creation_time_changes() {
        let expected = ProcessIdentityKey {
            pid: 1200,
            created_at: 100,
        };
        let reused = ProcessIdentityKey {
            pid: 1200,
            created_at: 101,
        };

        assert!(!process_identity_matches(expected, reused));
    }

    #[test]
    fn process_identity_requires_pid_and_creation_time() {
        let expected = ProcessIdentityKey {
            pid: 1200,
            created_at: 100,
        };
        assert!(process_identity_matches(expected, expected));
        assert!(!process_identity_matches(
            expected,
            ProcessIdentityKey {
                pid: 1201,
                created_at: 100,
            }
        ));
    }

    #[test]
    fn tid_reuse_is_rejected_when_owner_or_creation_time_changes() {
        let owner = ProcessIdentityKey {
            pid: 1200,
            created_at: 100,
        };
        let expected = ThreadIdentityKey {
            tid: 77,
            owner,
            created_at: 500,
        };
        assert!(!thread_identity_matches(
            expected,
            ThreadHandleIdentity {
                tid: 77,
                owner_pid: 2200,
                created_at: 500,
            }
        ));
        assert!(!thread_identity_matches(
            expected,
            ThreadHandleIdentity {
                tid: 77,
                owner_pid: 1200,
                created_at: 501,
            }
        ));
    }

    #[test]
    fn descendant_pid_reuse_is_rejected_before_its_thread_is_suspended() {
        let captured_descendant = ProcessIdentityKey {
            pid: 2200,
            created_at: 100,
        };
        let reused_descendant = ProcessIdentityKey {
            pid: 2200,
            created_at: 101,
        };

        assert!(thread_owner_binding_matches(
            captured_descendant,
            captured_descendant,
            2200,
        ));
        assert!(!thread_owner_binding_matches(
            captured_descendant,
            reused_descendant,
            2200,
        ));
    }

    #[test]
    fn descendant_must_start_after_its_stable_parent() {
        let parent = ProcessIdentityKey {
            pid: 1200,
            created_at: 100,
        };
        let stale_child = ProcessIdentityKey {
            pid: 2200,
            created_at: 99,
        };

        assert!(!valid_parent_child_identity(parent, stale_child));
    }

    #[test]
    fn only_no_more_files_finishes_snapshot_enumeration_normally() {
        assert!(matches!(
            classify_snapshot_error(ERROR_NO_MORE_FILES),
            Ok(false)
        ));

        let error = classify_snapshot_error(5).expect_err("access denied is not end-of-snapshot");
        assert!(matches!(
            error,
            ProcessControlError::Os(ref error) if error.raw_os_error() == Some(5)
        ));
    }

    #[test]
    fn missing_root_pid_cannot_capture_an_identity() {
        assert!(ProcessIdentity::capture(u32::MAX).is_err());
    }

    #[test]
    fn captured_root_identity_validates_and_a_tampered_identity_fails_closed() {
        let mut identity =
            ProcessIdentity::capture(std::process::id()).expect("capture current process");
        validate_process_identity(&identity).expect("current process identity");

        identity.key.created_at = identity.key.created_at.wrapping_add(1);
        assert!(matches!(
            validate_process_identity(&identity),
            Err(ProcessControlError::IdentityMismatch)
        ));
    }
}
