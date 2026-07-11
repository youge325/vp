#[cfg(not(windows))]
fn main() {
    eprintln!("run-hidden-desktop is only supported on Windows");
    std::process::exit(1);
}

#[cfg(windows)]
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

#[cfg(windows)]
fn run() -> Result<(), String> {
    use std::ffi::c_void;
    use std::ptr::{null, null_mut};

    type Handle = *mut c_void;
    type Bool = i32;
    type Dword = u32;
    type Lpwstr = *mut u16;
    type Lpcwstr = *const u16;

    #[repr(C)]
    struct StartupInfoW {
        cb: Dword,
        lp_reserved: Lpwstr,
        lp_desktop: Lpwstr,
        lp_title: Lpwstr,
        dw_x: Dword,
        dw_y: Dword,
        dw_x_size: Dword,
        dw_y_size: Dword,
        dw_x_count_chars: Dword,
        dw_y_count_chars: Dword,
        dw_fill_attribute: Dword,
        dw_flags: Dword,
        w_show_window: u16,
        cb_reserved2: u16,
        lp_reserved2: *mut u8,
        h_std_input: Handle,
        h_std_output: Handle,
        h_std_error: Handle,
    }

    #[repr(C)]
    struct ProcessInformation {
        h_process: Handle,
        h_thread: Handle,
        dw_process_id: Dword,
        dw_thread_id: Dword,
    }

    #[link(name = "user32")]
    extern "system" {
        fn CreateDesktopW(
            lpsz_desktop: Lpcwstr,
            lpsz_device: Lpcwstr,
            p_devmode: *mut c_void,
            dw_flags: Dword,
            dw_desired_access: Dword,
            lpsa: *mut c_void,
        ) -> Handle;
        fn CloseDesktop(h_desktop: Handle) -> Bool;
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn CreateProcessW(
            lp_application_name: Lpcwstr,
            lp_command_line: Lpwstr,
            lp_process_attributes: *mut c_void,
            lp_thread_attributes: *mut c_void,
            b_inherit_handles: Bool,
            dw_creation_flags: Dword,
            lp_environment: *mut c_void,
            lp_current_directory: Lpcwstr,
            lp_startup_info: *mut StartupInfoW,
            lp_process_information: *mut ProcessInformation,
        ) -> Bool;
        fn CloseHandle(h_object: Handle) -> Bool;
        fn GetExitCodeProcess(h_process: Handle, lp_exit_code: *mut Dword) -> Bool;
        fn GetLastError() -> Dword;
        fn GetStdHandle(n_std_handle: Dword) -> Handle;
        fn WaitForSingleObject(h_handle: Handle, dw_milliseconds: Dword) -> Dword;
    }

    const DESKTOP_ALL_ACCESS: Dword = 0x000F_01FF;
    const STARTF_USESTDHANDLES: Dword = 0x0000_0100;
    const STD_INPUT_HANDLE: Dword = -10i32 as Dword;
    const STD_OUTPUT_HANDLE: Dword = -11i32 as Dword;
    const STD_ERROR_HANDLE: Dword = -12i32 as Dword;
    const INFINITE: Dword = 0xFFFF_FFFF;

    let mut args = std::env::args_os().skip(1);
    let cwd = args
        .next()
        .ok_or_else(|| "usage: run-hidden-desktop <cwd> <command> [args...]".to_string())?;
    let command: Vec<_> = args.collect();
    if command.is_empty() {
        return Err("usage: run-hidden-desktop <cwd> <command> [args...]".to_string());
    }

    let desktop_name = format!("vp-e2e-{}", std::process::id());
    let mut desktop_name_w = wide(&desktop_name);
    let desktop = unsafe {
        CreateDesktopW(
            desktop_name_w.as_ptr(),
            null(),
            null_mut(),
            0,
            DESKTOP_ALL_ACCESS,
            null_mut(),
        )
    };
    if desktop.is_null() {
        return Err(format!("CreateDesktopW failed: {}", unsafe { GetLastError() }));
    }

    let command_line = command
        .iter()
        .map(|arg| quote_arg(&arg.to_string_lossy()))
        .collect::<Vec<_>>()
        .join(" ");
    let mut command_line_w = wide(&command_line);
    let cwd_w = wide_os(&cwd);

    let mut startup_info = StartupInfoW {
        cb: std::mem::size_of::<StartupInfoW>() as Dword,
        lp_reserved: null_mut(),
        lp_desktop: desktop_name_w.as_mut_ptr(),
        lp_title: null_mut(),
        dw_x: 0,
        dw_y: 0,
        dw_x_size: 0,
        dw_y_size: 0,
        dw_x_count_chars: 0,
        dw_y_count_chars: 0,
        dw_fill_attribute: 0,
        dw_flags: STARTF_USESTDHANDLES,
        w_show_window: 0,
        cb_reserved2: 0,
        lp_reserved2: null_mut(),
        h_std_input: unsafe { GetStdHandle(STD_INPUT_HANDLE) },
        h_std_output: unsafe { GetStdHandle(STD_OUTPUT_HANDLE) },
        h_std_error: unsafe { GetStdHandle(STD_ERROR_HANDLE) },
    };
    let mut process_info = ProcessInformation {
        h_process: null_mut(),
        h_thread: null_mut(),
        dw_process_id: 0,
        dw_thread_id: 0,
    };

    let created = unsafe {
        CreateProcessW(
            null(),
            command_line_w.as_mut_ptr(),
            null_mut(),
            null_mut(),
            1,
            0,
            null_mut(),
            cwd_w.as_ptr(),
            &mut startup_info,
            &mut process_info,
        )
    };
    if created == 0 {
        let error = unsafe { GetLastError() };
        unsafe {
            CloseDesktop(desktop);
        }
        return Err(format!("CreateProcessW failed: {error}; command: {command_line}"));
    }

    unsafe {
        CloseHandle(process_info.h_thread);
        WaitForSingleObject(process_info.h_process, INFINITE);
    }

    let mut exit_code = 1;
    unsafe {
        GetExitCodeProcess(process_info.h_process, &mut exit_code);
        CloseHandle(process_info.h_process);
        CloseDesktop(desktop);
    }
    std::process::exit(exit_code as i32);
}

#[cfg(windows)]
fn wide(value: &str) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    std::ffi::OsStr::new(value)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect()
}

#[cfg(windows)]
fn wide_os(value: &std::ffi::OsStr) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    value.encode_wide().chain(std::iter::once(0)).collect()
}

#[cfg(windows)]
fn quote_arg(arg: &str) -> String {
    if !arg.is_empty() && !arg.bytes().any(|b| b == b' ' || b == b'\t' || b == b'"') {
        return arg.to_string();
    }

    let mut quoted = String::from("\"");
    let mut backslashes = 0;
    for ch in arg.chars() {
        match ch {
            '\\' => backslashes += 1,
            '"' => {
                quoted.push_str(&"\\".repeat(backslashes * 2 + 1));
                quoted.push('"');
                backslashes = 0;
            }
            _ => {
                quoted.push_str(&"\\".repeat(backslashes));
                quoted.push(ch);
                backslashes = 0;
            }
        }
    }
    quoted.push_str(&"\\".repeat(backslashes * 2));
    quoted.push('"');
    quoted
}
