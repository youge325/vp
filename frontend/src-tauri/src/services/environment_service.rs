use tauri::{AppHandle, Runtime};

use crate::error::ShellError;
use crate::models::{EnvironmentCheckPayload, EnvironmentCheckResult};
use crate::persistence;
use crate::runtime::resolve_runtime_paths;
use crate::tasks;

pub async fn check_environment<R: Runtime>(
    app: AppHandle<R>,
    force_refresh: bool,
) -> Result<EnvironmentCheckPayload, ShellError> {
    let paths = resolve_runtime_paths(&app)?;
    let fingerprint = persistence::build_environment_fingerprint(&paths).ok();
    let app_data_dir = persistence::app_data_dir(&app).ok();

    if let (Some(data_dir), Some(fingerprint)) = (app_data_dir.as_deref(), fingerprint.as_deref()) {
        if let Some(cached) =
            persistence::load_environment_cache(data_dir, fingerprint, force_refresh)
        {
            let result =
                serde_json::from_value::<EnvironmentCheckResult>(cached.result).map_err(|error| {
                    ShellError::SchemaValidation(format!(
                        "Unable to deserialize cached environment check: {error}"
                    ))
                })?;
            return Ok(EnvironmentCheckPayload {
                result,
                source: String::from("cache"),
                checked_at: cached.checked_at,
            });
        }
    }

    let raw = tasks::run_single_cli_command(&app, &[String::from("check")]).await?;
    let result = serde_json::from_value::<EnvironmentCheckResult>(raw).map_err(|error| {
        ShellError::SchemaValidation(format!(
            "Unable to deserialize environment check result: {error}"
        ))
    })?;
    let checked_at = persistence::current_timestamp()?;

    if let (Some(data_dir), Some(fingerprint)) = (app_data_dir.as_deref(), fingerprint.as_deref()) {
        let serialized = serde_json::to_value(&result).map_err(|error| {
            ShellError::SchemaValidation(format!(
                "Unable to serialize environment check result for cache: {error}"
            ))
        })?;
        let _ = persistence::save_environment_cache(data_dir, &checked_at, fingerprint, &serialized);
    }

    Ok(EnvironmentCheckPayload {
        result,
        source: String::from("probe"),
        checked_at,
    })
}
