use tauri::{AppHandle, Runtime};

use crate::models::WorkbenchPreset;
use crate::persistence::{
    app_data_dir,
    load_workbench_preset as load_preset,
    save_workbench_preset as save_preset,
};

#[tauri::command]
pub async fn load_workbench_preset<R: Runtime>(
    app: AppHandle<R>,
) -> Result<Option<WorkbenchPreset>, String> {
    let data_dir = app_data_dir(&app)?;
    Ok(load_preset(&data_dir))
}

#[tauri::command]
pub async fn save_workbench_preset<R: Runtime>(
    app: AppHandle<R>,
    preset: WorkbenchPreset,
) -> Result<(), String> {
    let data_dir = app_data_dir(&app)?;
    save_preset(&data_dir, &preset)
}
