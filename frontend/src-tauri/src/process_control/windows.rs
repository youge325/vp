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

trait Win32ProcessApi {
    fn last_error(&self) -> u32;
    fn create_toolhelp_snapshot(&self, flags: u32) -> HANDLE;
    fn process_first(&self, snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32;
    fn process_next(&self, snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32;
    fn thread_first(&self, snapshot: HANDLE, entry: &mut THREADENTRY32) -> i32;
    fn thread_next(&self, snapshot: HANDLE, entry: &mut THREADENTRY32) -> i32;
    fn open_process(&self, access: u32, pid: u32) -> HANDLE;
    fn open_thread(&self, access: u32, tid: u32) -> HANDLE;
    fn process_id(&self, handle: HANDLE) -> u32;
    fn process_id_of_thread(&self, handle: HANDLE) -> u32;
    fn thread_id(&self, handle: HANDLE) -> u32;
    fn process_creation_time(&self, handle: HANDLE) -> Result<u64, io::Error>;
    fn thread_creation_time(&self, handle: HANDLE) -> Result<u64, io::Error>;
    fn wait_for_single_object(&self, handle: HANDLE, milliseconds: u32) -> u32;
    fn suspend_thread(&self, handle: HANDLE) -> u32;
    fn resume_thread(&self, handle: HANDLE) -> u32;
}

#[derive(Clone, Copy)]
struct SystemWin32ProcessApi;

const SYSTEM_API: SystemWin32ProcessApi = SystemWin32ProcessApi;

impl Win32ProcessApi for SystemWin32ProcessApi {
    fn last_error(&self) -> u32 {
        unsafe { GetLastError() }
    }

    fn create_toolhelp_snapshot(&self, flags: u32) -> HANDLE {
        unsafe { CreateToolhelp32Snapshot(flags, 0) }
    }

    fn process_first(&self, snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32 {
        unsafe { Process32FirstW(snapshot, entry) }
    }

    fn process_next(&self, snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32 {
        unsafe { Process32NextW(snapshot, entry) }
    }

    fn thread_first(&self, snapshot: HANDLE, entry: &mut THREADENTRY32) -> i32 {
        unsafe { Thread32First(snapshot, entry) }
    }

    fn thread_next(&self, snapshot: HANDLE, entry: &mut THREADENTRY32) -> i32 {
        unsafe { Thread32Next(snapshot, entry) }
    }

    fn open_process(&self, access: u32, pid: u32) -> HANDLE {
        unsafe { OpenProcess(access, 0, pid) }
    }

    fn open_thread(&self, access: u32, tid: u32) -> HANDLE {
        unsafe { OpenThread(access, 0, tid) }
    }

    fn process_id(&self, handle: HANDLE) -> u32 {
        unsafe { GetProcessId(handle) }
    }

    fn process_id_of_thread(&self, handle: HANDLE) -> u32 {
        unsafe { GetProcessIdOfThread(handle) }
    }

    fn thread_id(&self, handle: HANDLE) -> u32 {
        unsafe { GetThreadId(handle) }
    }

    fn process_creation_time(&self, handle: HANDLE) -> Result<u64, io::Error> {
        system_creation_time(handle, GetProcessTimes)
    }

    fn thread_creation_time(&self, handle: HANDLE) -> Result<u64, io::Error> {
        system_creation_time(handle, GetThreadTimes)
    }

    fn wait_for_single_object(&self, handle: HANDLE, milliseconds: u32) -> u32 {
        unsafe { WaitForSingleObject(handle, milliseconds) }
    }

    fn suspend_thread(&self, handle: HANDLE) -> u32 {
        unsafe { SuspendThread(handle) }
    }

    fn resume_thread(&self, handle: HANDLE) -> u32 {
        unsafe { ResumeThread(handle) }
    }
}

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

pub(super) struct ProcessIdentity {
    key: ProcessIdentityKey,
    handle: OwnedHandle,
}

impl ProcessIdentity {
    pub(super) fn capture(root_pid: u32) -> Result<Self, ProcessControlError> {
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

pub(super) struct SuspendedThreads {
    threads: Vec<SuspendedThread>,
}

/// Suspend the stable root process tree. A second pass catches descendants
/// created during the first snapshot, while exact creation-time identities
/// prevent a recycled TID from being mistaken for an already-suspended thread.
pub(super) fn suspend_process_tree(
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
            return Err(failure_after_rollback(error, &mut threads));
        }
    };
    match set_threads_suspended(&pids_after, Some(&already)) {
        Ok(mut new_threads) => threads.append(&mut new_threads),
        Err(error) => {
            return Err(failure_after_rollback(error, &mut threads));
        }
    }

    if let Err(error) = validate_process_identity(identity) {
        return Err(failure_after_rollback(error, &mut threads));
    }
    Ok(SuspendedThreads { threads })
}

/// Resume only the exact thread handles retained by the matching suspend.
///
/// Successful or exited threads are removed from the cache immediately. If a
/// live thread fails to resume its handle remains cached, so a retry cannot
/// decrement the suspend count of threads that were already resumed.
pub(super) fn resume_process_tree(
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

pub(super) fn validate_process_identity(
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
    let raw = SYSTEM_API.open_process(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SYNCHRONIZE, pid);
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
    let raw = SYSTEM_API.open_thread(
        THREAD_SUSPEND_RESUME | THREAD_QUERY_LIMITED_INFORMATION | THREAD_SYNCHRONIZE,
        tid,
    );
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
    read_process_identity_with(&SYSTEM_API, raw_handle(handle))
}

fn read_process_identity_with(
    api: &impl Win32ProcessApi,
    handle: HANDLE,
) -> Result<ProcessIdentityKey, ProcessControlError> {
    let pid = api.process_id(handle);
    if pid == 0 {
        return Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            api.last_error() as i32,
        )));
    }
    Ok(ProcessIdentityKey {
        pid,
        created_at: api
            .process_creation_time(handle)
            .map_err(ProcessControlError::Os)?,
    })
}

fn read_thread_identity(handle: &OwnedHandle) -> Result<ThreadHandleIdentity, ProcessControlError> {
    read_thread_identity_with(&SYSTEM_API, raw_handle(handle))
}

fn read_thread_identity_with(
    api: &impl Win32ProcessApi,
    handle: HANDLE,
) -> Result<ThreadHandleIdentity, ProcessControlError> {
    let tid = api.thread_id(handle);
    if tid == 0 {
        return Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            api.last_error() as i32,
        )));
    }
    let owner_pid = api.process_id_of_thread(handle);
    if owner_pid == 0 {
        return Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            api.last_error() as i32,
        )));
    }
    Ok(ThreadHandleIdentity {
        tid,
        owner_pid,
        created_at: api
            .thread_creation_time(handle)
            .map_err(ProcessControlError::Os)?,
    })
}

fn system_creation_time(
    handle: HANDLE,
    get_times: unsafe extern "system" fn(
        HANDLE,
        *mut FILETIME,
        *mut FILETIME,
        *mut FILETIME,
        *mut FILETIME,
    ) -> i32,
) -> Result<u64, io::Error> {
    let mut creation = FILETIME::default();
    let mut exit = FILETIME::default();
    let mut kernel = FILETIME::default();
    let mut user = FILETIME::default();
    if unsafe { get_times(handle, &mut creation, &mut exit, &mut kernel, &mut user) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok((u64::from(creation.dwHighDateTime) << 32) | u64::from(creation.dwLowDateTime))
}

fn ensure_handle_is_live(handle: &OwnedHandle) -> Result<(), ProcessControlError> {
    ensure_raw_handle_is_live(&SYSTEM_API, raw_handle(handle))
}

fn ensure_raw_handle_is_live(
    api: &impl Win32ProcessApi,
    handle: HANDLE,
) -> Result<(), ProcessControlError> {
    let result = api.wait_for_single_object(handle, 0);
    let last_error = (result == WAIT_FAILED).then(|| api.last_error());
    classify_wait_result(result, last_error)
}

fn classify_wait_result(result: u32, last_error: Option<u32>) -> Result<(), ProcessControlError> {
    match result {
        WAIT_TIMEOUT => Ok(()),
        WAIT_OBJECT_0 => Err(ProcessControlError::NotFound),
        WAIT_FAILED => Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            last_error.unwrap_or_default() as i32,
        ))),
        _ => Err(ProcessControlError::Os(io::Error::other(
            "unexpected process wait result",
        ))),
    }
}

fn snapshot_process_parents() -> Result<BTreeMap<u32, u32>, ProcessControlError> {
    let snapshot = SnapshotHandle::processes()?;
    snapshot_process_parents_with(&SYSTEM_API, snapshot.raw())
}

fn snapshot_process_parents_with(
    api: &impl Win32ProcessApi,
    snapshot: HANDLE,
) -> Result<BTreeMap<u32, u32>, ProcessControlError> {
    let mut entries = BTreeMap::new();
    let mut entry = PROCESSENTRY32W {
        dwSize: size_of::<PROCESSENTRY32W>() as u32,
        ..unsafe { std::mem::zeroed() }
    };

    let mut has_entry = snapshot_result(api, api.process_first(snapshot, &mut entry))?;
    while has_entry {
        entries.insert(entry.th32ProcessID, entry.th32ParentProcessID);
        has_entry = snapshot_result(api, api.process_next(snapshot, &mut entry))?;
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

    let mut has_entry = snapshot_result(
        &SYSTEM_API,
        SYSTEM_API.thread_first(snapshot.raw(), &mut entry),
    )?;
    while has_entry {
        if let Some(owner) = tree.processes.get(&entry.th32OwnerProcessID) {
            match open_thread(entry.th32ThreadID, owner) {
                Ok(thread) if exclude.is_some_and(|keys| keys.contains(&thread.key)) => {}
                Ok(thread) => match set_open_thread_suspended(&thread, true) {
                    Ok(()) => touched.push(thread),
                    Err(error) => {
                        return Err(failure_after_rollback(error, &mut touched));
                    }
                },
                Err(error) => {
                    return Err(failure_after_rollback(error, &mut touched));
                }
            }
        }
        has_entry = match snapshot_result(
            &SYSTEM_API,
            SYSTEM_API.thread_next(snapshot.raw(), &mut entry),
        ) {
            Ok(has_entry) => has_entry,
            Err(error) => {
                return Err(failure_after_rollback(error, &mut touched));
            }
        };
    }

    if let Err(error) = tree.validate() {
        return Err(failure_after_rollback(error, &mut touched));
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
    set_open_thread_suspended_with(&SYSTEM_API, thread, suspend)
}

fn set_open_thread_suspended_with(
    api: &impl Win32ProcessApi,
    thread: &SuspendedThread,
    suspend: bool,
) -> Result<(), ProcessControlError> {
    let observed = read_thread_identity(&thread.handle)?;
    if !thread_identity_matches(thread.key, observed) {
        return Err(ProcessControlError::IdentityMismatch);
    }
    if !suspend {
        ensure_raw_handle_is_live(api, raw_handle(&thread.handle))?;
    }
    set_raw_thread_suspended(api, raw_handle(&thread.handle), suspend)
}

fn set_raw_thread_suspended(
    api: &impl Win32ProcessApi,
    handle: HANDLE,
    suspend: bool,
) -> Result<(), ProcessControlError> {
    let result = if suspend {
        api.suspend_thread(handle)
    } else {
        api.resume_thread(handle)
    };
    if result == u32::MAX {
        return Err(ProcessControlError::Os(io::Error::from_raw_os_error(
            api.last_error() as i32,
        )));
    }
    Ok(())
}

fn rollback_suspended_threads(
    threads: &mut Vec<SuspendedThread>,
) -> Result<(), ProcessControlError> {
    rollback_items(
        threads,
        |thread| set_open_thread_suspended_with(&SYSTEM_API, thread, false),
        |thread| format!("thread {}", thread.key.tid),
    )
}

fn rollback_items<T>(
    items: &mut Vec<T>,
    mut resume: impl FnMut(&T) -> Result<(), ProcessControlError>,
    mut describe: impl FnMut(&T) -> String,
) -> Result<(), ProcessControlError> {
    let mut failures = Vec::new();
    for item in items.drain(..) {
        match resume(&item) {
            Ok(()) | Err(ProcessControlError::NotFound) => {}
            Err(error) => failures.push(format!("{}: {error}", describe(&item))),
        }
    }
    if failures.is_empty() {
        Ok(())
    } else {
        Err(ProcessControlError::StateUnknown(format!(
            "failed to resume threads during rollback: {}",
            failures.join("; ")
        )))
    }
}

fn failure_after_rollback(
    primary: ProcessControlError,
    threads: &mut Vec<SuspendedThread>,
) -> ProcessControlError {
    combine_control_and_rollback_error(primary, rollback_suspended_threads(threads))
}

fn combine_control_and_rollback_error(
    primary: ProcessControlError,
    rollback: Result<(), ProcessControlError>,
) -> ProcessControlError {
    match rollback {
        Ok(()) => primary,
        Err(rollback_error) => ProcessControlError::StateUnknown(format!(
            "primary failure: {primary}; rollback failure: {rollback_error}"
        )),
    }
}

fn snapshot_result(api: &impl Win32ProcessApi, result: i32) -> Result<bool, ProcessControlError> {
    if result != 0 {
        return Ok(true);
    }
    classify_snapshot_error(api.last_error())
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
        let raw = SYSTEM_API.create_toolhelp_snapshot(flags);
        Ok(Self(owned_handle(raw)?))
    }

    fn raw(&self) -> HANDLE {
        raw_handle(&self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::{Cell, RefCell};
    use std::collections::VecDeque;

    enum ProcessStep {
        Entry { pid: u32, parent_pid: u32 },
        Error(u32),
        End,
    }

    struct FakeWin32ProcessApi {
        last_error: Cell<u32>,
        process_steps: RefCell<VecDeque<ProcessStep>>,
        wait_result: Cell<u32>,
        resume_results: RefCell<VecDeque<u32>>,
    }

    impl FakeWin32ProcessApi {
        fn new(process_steps: impl IntoIterator<Item = ProcessStep>) -> Self {
            Self {
                last_error: Cell::new(ERROR_NO_MORE_FILES),
                process_steps: RefCell::new(process_steps.into_iter().collect()),
                wait_result: Cell::new(WAIT_TIMEOUT),
                resume_results: RefCell::new(VecDeque::new()),
            }
        }

        fn next_process(&self, entry: &mut PROCESSENTRY32W) -> i32 {
            match self.process_steps.borrow_mut().pop_front() {
                Some(ProcessStep::Entry { pid, parent_pid }) => {
                    entry.th32ProcessID = pid;
                    entry.th32ParentProcessID = parent_pid;
                    1
                }
                Some(ProcessStep::Error(code)) => {
                    self.last_error.set(code);
                    0
                }
                Some(ProcessStep::End) | None => {
                    self.last_error.set(ERROR_NO_MORE_FILES);
                    0
                }
            }
        }
    }

    impl Win32ProcessApi for FakeWin32ProcessApi {
        fn last_error(&self) -> u32 {
            self.last_error.get()
        }

        fn create_toolhelp_snapshot(&self, _flags: u32) -> HANDLE {
            std::ptr::null_mut()
        }

        fn process_first(&self, _snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32 {
            self.next_process(entry)
        }

        fn process_next(&self, _snapshot: HANDLE, entry: &mut PROCESSENTRY32W) -> i32 {
            self.next_process(entry)
        }

        fn thread_first(&self, _snapshot: HANDLE, _entry: &mut THREADENTRY32) -> i32 {
            unreachable!("thread enumeration was not requested")
        }

        fn thread_next(&self, _snapshot: HANDLE, _entry: &mut THREADENTRY32) -> i32 {
            unreachable!("thread enumeration was not requested")
        }

        fn open_process(&self, _access: u32, _pid: u32) -> HANDLE {
            std::ptr::null_mut()
        }

        fn open_thread(&self, _access: u32, _tid: u32) -> HANDLE {
            std::ptr::null_mut()
        }

        fn process_id(&self, _handle: HANDLE) -> u32 {
            1
        }

        fn process_id_of_thread(&self, _handle: HANDLE) -> u32 {
            1
        }

        fn thread_id(&self, _handle: HANDLE) -> u32 {
            1
        }

        fn process_creation_time(&self, _handle: HANDLE) -> Result<u64, io::Error> {
            Ok(1)
        }

        fn thread_creation_time(&self, _handle: HANDLE) -> Result<u64, io::Error> {
            Ok(1)
        }

        fn wait_for_single_object(&self, _handle: HANDLE, _milliseconds: u32) -> u32 {
            self.wait_result.get()
        }

        fn suspend_thread(&self, _handle: HANDLE) -> u32 {
            unreachable!("suspend was not requested")
        }

        fn resume_thread(&self, _handle: HANDLE) -> u32 {
            let result = self.resume_results.borrow_mut().pop_front().unwrap_or(0);
            if result == u32::MAX {
                self.last_error.set(5);
            }
            result
        }
    }

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
    fn injected_toolhelp_failure_in_the_middle_of_enumeration_is_not_an_end_marker() {
        let api = FakeWin32ProcessApi::new([
            ProcessStep::Entry {
                pid: 100,
                parent_pid: 1,
            },
            ProcessStep::Error(5),
        ]);

        let error = snapshot_process_parents_with(&api, std::ptr::null_mut())
            .expect_err("access denied must abort enumeration");
        assert!(matches!(
            error,
            ProcessControlError::Os(ref error) if error.raw_os_error() == Some(5)
        ));
    }

    #[test]
    fn injected_toolhelp_end_marker_finishes_the_snapshot() {
        let api = FakeWin32ProcessApi::new([
            ProcessStep::Entry {
                pid: 100,
                parent_pid: 1,
            },
            ProcessStep::End,
        ]);

        assert_eq!(
            snapshot_process_parents_with(&api, std::ptr::null_mut()).expect("snapshot"),
            BTreeMap::from([(100, 1)])
        );
    }

    #[test]
    fn wait_failed_preserves_the_original_os_error() {
        let api = FakeWin32ProcessApi::new([]);
        api.wait_result.set(WAIT_FAILED);
        api.last_error.set(5);
        let error =
            ensure_raw_handle_is_live(&api, std::ptr::null_mut()).expect_err("wait must fail");
        assert!(matches!(
            error,
            ProcessControlError::Os(ref error) if error.raw_os_error() == Some(5)
        ));
    }

    #[test]
    fn rollback_failure_marks_process_state_unknown() {
        let api = FakeWin32ProcessApi::new([]);
        api.resume_results.borrow_mut().extend([0, u32::MAX]);
        let mut handles = vec![std::ptr::null_mut(), 1usize as HANDLE];
        let rollback = rollback_items(
            &mut handles,
            |handle| set_raw_thread_suspended(&api, *handle, false),
            |_| "thread".to_string(),
        );
        let combined =
            combine_control_and_rollback_error(ProcessControlError::IdentityMismatch, rollback);

        assert!(handles.is_empty());
        assert!(matches!(
            combined,
            ProcessControlError::StateUnknown(ref message)
                if message.contains("identity changed") && message.contains("rollback failure")
        ));
    }

    #[test]
    fn successful_rollback_preserves_the_primary_error() {
        let combined =
            combine_control_and_rollback_error(ProcessControlError::IdentityMismatch, Ok(()));
        assert!(matches!(combined, ProcessControlError::IdentityMismatch));
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
