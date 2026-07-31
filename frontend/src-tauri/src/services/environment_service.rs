use tauri::State;

use crate::error::ShellError;
use crate::generated::{CheckEnvironmentInvocation, CheckEnvironmentSpec};
use crate::models::EnvironmentCheckPayload;
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
    persistence::resolve_environment_cache(
        &paths.app_data_dir,
        &fingerprint,
        force_refresh,
        || async {
            tasks::run_single_cli_command::<CheckEnvironmentSpec>(
                &paths,
                &CheckEnvironmentInvocation,
            )
            .await
        },
    )
    .await
}
