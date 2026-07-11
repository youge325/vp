#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{env, process};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn main() {
    let driver = match env::var_os("VP_EDGE_DRIVER_PATH") {
        Some(path) => path,
        None => {
            eprintln!("VP_EDGE_DRIVER_PATH is not set");
            process::exit(2);
        }
    };

    let mut command = process::Command::new(driver);
    command.args(env::args_os().skip(1));

    #[cfg(windows)]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }

    match command.status() {
        Ok(status) => process::exit(status.code().unwrap_or(1)),
        Err(error) => {
            eprintln!("failed to start msedgedriver: {error}");
            process::exit(1);
        }
    }
}
