use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{EnvironmentCheckPayload, EnvironmentCheckResult, EnvironmentCheckSource};
use crate::persistence;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks;

/// Tauri command wrapper. The ``forceRefresh`` argument name must stay
/// camelCase to match the frontend payload because Rust ``rename_all`` cannot
/// rewrite Tauri command parameter names.
#[tauri::command]
#[allow(non_snake_case)]
pub(crate) async fn check_environment<R: Runtime>(
    app: AppHandle<R>,
    paths: State<'_, ResolvedRuntimePaths>,
    forceRefresh: bool,
) -> Result<EnvironmentCheckPayload, ShellError> {
    let paths = paths.inner().clone();
    check_environment_impl(app, paths, forceRefresh).await
}

async fn check_environment_impl<R: Runtime>(
    app: AppHandle<R>,
    paths: ResolvedRuntimePaths,
    force_refresh: bool,
) -> Result<EnvironmentCheckPayload, ShellError> {
    let fingerprint = persistence::build_environment_fingerprint(&paths)
        .await
        .ok();
    let app_data_dir = persistence::app_data_dir(&app).await.ok();

    if let (Some(data_dir), Some(fingerprint)) = (app_data_dir.as_deref(), fingerprint.as_deref()) {
        if let Some((checked_at, cached_result)) =
            persistence::load_environment_cache(data_dir, fingerprint, force_refresh).await
        {
            let result = serde_json::from_value::<EnvironmentCheckResult>(cached_result).map_err(
                |error| {
                    ShellError::SchemaValidation(format!(
                        "Unable to deserialize cached environment check: {error}"
                    ))
                },
            )?;
            return Ok(EnvironmentCheckPayload {
                result,
                source: EnvironmentCheckSource::Cache,
                checked_at,
            });
        }
    }

    let raw = tasks::run_single_cli_command(&paths, &[String::from("check")], None).await?;
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
        let _ =
            persistence::save_environment_cache(data_dir, &checked_at, fingerprint, &serialized)
                .await;
    }

    Ok(EnvironmentCheckPayload {
        result,
        source: EnvironmentCheckSource::Probe,
        checked_at,
    })
}
