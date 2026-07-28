use tauri::State;

use crate::error::ShellError;
use crate::models::WorkbenchPreset;
use crate::persistence::{
    load_workbench_preset as load_preset, save_workbench_preset as save_preset,
};
use crate::runtime::ResolvedRuntimePaths;

#[tauri::command]
pub(crate) async fn load_workbench_preset(
    paths: State<'_, ResolvedRuntimePaths>,
) -> Result<Option<WorkbenchPreset>, ShellError> {
    load_preset(&paths.app_data_dir).await
}

#[tauri::command]
pub(crate) async fn save_workbench_preset(
    paths: State<'_, ResolvedRuntimePaths>,
    preset: WorkbenchPreset,
) -> Result<(), ShellError> {
    save_preset(&paths.app_data_dir, &preset).await
}
