//! Native file/folder picker commands.
//!
//! Uses ``rfd::AsyncFileDialog`` so the dialog future yields back to the
//! tokio runtime instead of blocking a worker thread the way the
//! synchronous ``rfd::FileDialog`` does.

use std::path::PathBuf;

use rfd::AsyncFileDialog;

use crate::error::ShellError;

#[tauri::command]
pub async fn pick_inputs() -> Result<Vec<String>, ShellError> {
    let files = AsyncFileDialog::new()
        .set_title("Import Videos")
        .add_filter(
            "Video",
            &["mp4", "avi", "mkv", "mov", "flv", "webm", "wmv", "ts"],
        )
        .pick_files()
        .await
        .unwrap_or_default();

    Ok(files
        .into_iter()
        .map(|handle| handle.path().display().to_string())
        .collect())
}

#[tauri::command]
pub async fn pick_output_directory() -> Result<Option<String>, ShellError> {
    Ok(AsyncFileDialog::new()
        .set_title("Select Output Directory")
        .pick_folder()
        .await
        .map(|handle| handle.path().display().to_string()))
}

#[tauri::command]
pub async fn open_output_location(path: String) -> Result<(), ShellError> {
    let path_buf = PathBuf::from(path);
    let target = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf.parent().map(PathBuf::from).unwrap_or(path_buf)
    };
    // Phase 5e — route ``open::that_detached`` failures into the
    // dedicated [`ShellError::OpenLocation`] variant so the original
    // ``io::Error`` survives in the source chain instead of being
    // re-wrapped inside a synthetic ``io::Error::new(Other, ...)``.
    open::that_detached(target).map_err(ShellError::OpenLocation)
}
