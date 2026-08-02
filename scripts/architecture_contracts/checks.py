"""Aggregate independent repository architecture checks."""

from __future__ import annotations

from pathlib import Path

from .application_defaults import check_application_default_consumers
from .filter_contracts import check_filter_contract_consumers
from .catalog import RULES
from .ipc_checks import _check_command_surface
from .model_assets import check_model_asset_consumers
from .protocol_markers import check_protocol_marker_literals
from .python_checks import (
    _check_backend_package_cycles,
    _check_paddlegan_metadata,
    _check_python_algorithm_factory_registry,
    _check_python_boundary_field_consumers,
    _check_python_cli_commands,
    _check_python_module_exports,
    _check_python_package_reexports,
    _check_side_effect_free_python_packages,
    _check_typed_ndjson_error_emission,
)
from .rules import run_rules
from .rust_checks import (
    _check_rust_lifecycle_result_handling,
    _check_rust_model_reexports,
    _check_rust_package_cycles,
    _check_rust_public_surface,
    _check_rust_reaper_ownership,
    _check_rust_submodule_cycles,
    _check_rust_task_adapter_boundaries,
    _check_rust_unused_dependencies,
)
from .rust_visibility import check_rust_restricted_visibility
from .script_reachability import check_script_reachability
from .typescript_checks import (
    _check_frontend_dependency_boundaries,
    _check_frontend_global_css_classes,
    _check_frontend_protocol_reexports,
    _check_frontend_test_ids,
    _check_frontend_test_layout,
    _check_frontend_test_support_exports,
)


def collect_architecture_issues(root: Path) -> list[str]:
    issues = run_rules(root, RULES)
    issues.extend(_check_command_surface(root))
    issues.extend(check_protocol_marker_literals(root))
    issues.extend(_check_paddlegan_metadata(root))
    issues.extend(_check_python_algorithm_factory_registry(root))
    issues.extend(_check_python_cli_commands(root))
    issues.extend(_check_side_effect_free_python_packages(root))
    issues.extend(_check_python_boundary_field_consumers(root))
    issues.extend(_check_python_package_reexports(root))
    issues.extend(_check_python_module_exports(root))
    issues.extend(_check_frontend_test_layout(root))
    issues.extend(_check_frontend_dependency_boundaries(root))
    issues.extend(_check_frontend_protocol_reexports(root))
    issues.extend(_check_rust_model_reexports(root))
    issues.extend(_check_frontend_global_css_classes(root))
    issues.extend(_check_frontend_test_ids(root))
    issues.extend(_check_frontend_test_support_exports(root))
    issues.extend(_check_typed_ndjson_error_emission(root))
    issues.extend(_check_backend_package_cycles(root))
    issues.extend(_check_rust_package_cycles(root))
    issues.extend(_check_rust_submodule_cycles(root, "tasks"))
    issues.extend(_check_rust_task_adapter_boundaries(root))
    issues.extend(_check_rust_lifecycle_result_handling(root))
    issues.extend(_check_rust_reaper_ownership(root))
    issues.extend(_check_rust_unused_dependencies(root))
    issues.extend(_check_rust_public_surface(root))
    issues.extend(check_application_default_consumers(root))
    issues.extend(check_filter_contract_consumers(root))
    issues.extend(check_model_asset_consumers(root))
    issues.extend(check_script_reachability(root))
    issues.extend(check_rust_restricted_visibility(root))
    return issues
