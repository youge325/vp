use tauri::State;

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
pub(crate) async fn check_environment(
    paths: State<'_, ResolvedRuntimePaths>,
    forceRefresh: bool,
) -> Result<EnvironmentCheckPayload, ShellError> {
    let paths = paths.inner().clone();
    check_environment_impl(paths, forceRefresh).await
}

async fn check_environment_impl(
    paths: ResolvedRuntimePaths,
    force_refresh: bool,
) -> Result<EnvironmentCheckPayload, ShellError> {
    let fingerprint = persistence::build_environment_fingerprint(&paths).await?;

    if let Some((checked_at, result)) =
        persistence::load_environment_cache(&paths.app_data_dir, &fingerprint, force_refresh)
            .await?
    {
        return Ok(EnvironmentCheckPayload {
            result,
            source: EnvironmentCheckSource::Cache,
            checked_at,
        });
    }

    let result: EnvironmentCheckResult = tasks::run_single_cli_command(
        &paths,
        &[String::from("check")],
        None,
        "environment check result",
    )
    .await?;
    let checked_at = persistence::current_timestamp();

    persistence::save_environment_cache(&paths.app_data_dir, &checked_at, &fingerprint, &result)
        .await?;

    Ok(EnvironmentCheckPayload {
        result,
        source: EnvironmentCheckSource::Probe,
        checked_at,
    })
}
