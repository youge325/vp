use tauri::{AppHandle, Runtime, State};

use crate::error::ShellError;
use crate::models::{EnvironmentCheckPayload, EnvironmentCheckResult};
use crate::persistence;
use crate::runtime::ResolvedRuntimePaths;
use crate::tasks::{self, CliOutcome};

/// Tauri command wrapper.
///
/// Phase C.2.5 sank this here from ``lib.rs`` so the entry crate only owns
/// ``run()`` and integration tests. The ``forceRefresh`` argument name must
/// stay camelCase to match the frontend payload — Rust ``rename_all`` cannot
/// rewrite tauri command parameter names, so we ``#[allow(non_snake_case)]``.
#[tauri::command]
#[allow(non_snake_case)]
pub async fn check_environment<R: Runtime>(
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
    let fingerprint = persistence::build_environment_fingerprint(&paths).await.ok();
    let app_data_dir = persistence::app_data_dir(&app).await.ok();

    if let (Some(data_dir), Some(fingerprint)) = (app_data_dir.as_deref(), fingerprint.as_deref()) {
        if let Some(cached) =
            persistence::load_environment_cache(data_dir, fingerprint, force_refresh).await
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

    // Phase 5c — the one-shot runner now returns a [`CliOutcome`]; the
    // exhaustive match below replaces the previous ``?`` that silently
    // turned a backend error envelope into ``Ok(value)`` that then
    // failed downstream as a schema-mismatch.
    let outcome =
        tasks::run_single_cli_command(&app, &paths, &[String::from("check")], None).await?;
    let raw = match outcome {
        CliOutcome::Ok(value) => value,
        CliOutcome::FailedWithEnvelope(envelope) => {
            return Err(ShellError::BackendExit(format!(
                "{} ({:?})",
                envelope.message, envelope.code
            )));
        }
        CliOutcome::FailedWithoutEnvelope(message) => {
            return Err(ShellError::BackendExit(message));
        }
    };
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
        source: String::from("probe"),
        checked_at,
    })
}
