"""Reviewed dynamic Python boundaries and their executable evidence."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from architecture_contracts.python_ast import literal_string_pair_registry

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ReviewedExclusion:
    path: str
    reason: str
    evidence_file: str
    evidence_marker: str
    protects_reachability: bool = True


@dataclass(frozen=True, slots=True)
class ReviewedSymbol:
    """One exact dynamically consumed symbol that Vulture cannot resolve."""

    path: str
    symbol: str
    reason: str
    evidence_file: str
    evidence_marker: str


_RIFE_CATALOG = ROOT / "backend/app/catalog/rife_models.py"
_RIFE_PACKAGE = ROOT / "backend/app/algorithms/pytorch/rife"


def _read_rife_catalog_versions(catalog_path: Path = _RIFE_CATALOG) -> tuple[str, ...]:
    """Statically read the neutral catalog without importing backend runtime code."""
    tree = ast.parse(catalog_path.read_text(encoding="utf-8"), filename=str(catalog_path))
    groups: ast.expr | None = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_VERSION_GROUPS":
                groups = node.value
                break
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_VERSION_GROUPS" for target in node.targets
        ):
            groups = node.value
            break
    if not isinstance(groups, (ast.List, ast.Tuple)):
        raise RuntimeError("RIFE neutral catalog must define a literal _VERSION_GROUPS sequence")

    versions: list[str] = []
    for group in groups.elts:
        if not isinstance(group, ast.Tuple) or not group.elts:
            raise RuntimeError("RIFE neutral catalog contains a non-tuple version group")
        version_node = group.elts[0]
        try:
            group_versions = ast.literal_eval(version_node)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("RIFE neutral catalog version groups must be literal sequences") from exc
        if not isinstance(group_versions, (list, tuple)) or not all(
            isinstance(version, str) for version in group_versions
        ):
            raise RuntimeError("RIFE neutral catalog contains an invalid version sequence")
        versions.extend(group_versions)

    if not versions or len(versions) != len(set(versions)):
        raise RuntimeError("RIFE neutral catalog versions must be non-empty and unique")
    return tuple(versions)


def _rife_module_paths(catalog_path: Path = _RIFE_CATALOG) -> tuple[str, ...]:
    return tuple(
        f"backend/app/algorithms/pytorch/rife/ifnet_v{version.replace('.', '_')}.py"
        for version in _read_rife_catalog_versions(catalog_path)
    )


_STATIC_REVIEWED_EXCLUSIONS = (
    ReviewedExclusion(
        path="backend/app/generated/contracts.py",
        reason="Generated Pydantic bindings are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_boundary_schema",
    ),
    ReviewedExclusion(
        path="backend/app/generated/protocol_constants.py",
        reason="Generated protocol constants are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_python_protocol_constants",
    ),
    ReviewedExclusion(
        path="backend/app/generated/stage_worker_contracts.py",
        reason="Generated stage-worker bindings are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_stage_worker_schema",
        protects_reachability=False,
    ),
    ReviewedExclusion(
        path="backend/app/algorithms/paddle/paddlegan_vsr/vendor/",
        reason="Vendored PaddleGAN framework callbacks are reached dynamically by Paddle.",
        evidence_file="backend/tests/test_algorithms/test_paddlegan_vsr_specs.py",
        evidence_marker="test_vendor_auxiliary_weight_helper_uses_only_local_auxiliary_files",
    ),
)

_RIFE_REVIEWED_EXCLUSIONS = tuple(
    ReviewedExclusion(
        path=path,
        reason="RIFE model module is selected dynamically from the neutral version catalog.",
        evidence_file="backend/tests/test_algorithms/test_rife_all_models.py",
        evidence_marker="importlib.import_module(rife_package)",
    )
    for path in _rife_module_paths()
)

_REVIEWED_EXCLUSIONS = (*_STATIC_REVIEWED_EXCLUSIONS, *_RIFE_REVIEWED_EXCLUSIONS)

_PRODUCTION_REVIEWED_SYMBOLS = (
    ReviewedSymbol(
        path="backend/app/algorithms/pytorch/rife/onnx_export.py",
        symbol="forward",
        reason="PyTorch invokes the module forward method while tracing the ONNX export wrapper.",
        evidence_file="backend/tests/test_algorithms/test_rife_onnx.py",
        evidence_marker="class TestRIFEONNXExport",
    ),
    ReviewedSymbol(
        path="backend/app/algorithms/pytorch/rife/warplayer.py",
        symbol="warp",
        reason="The protected catalog-selected RIFE modules import and call this shared warp function.",
        evidence_file="backend/tests/test_algorithms/test_rife_all_models.py",
        evidence_marker="importlib.import_module(rife_package)",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/benchmark.py",
        symbol="cmd_benchmark",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_benchmark",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/check.py",
        symbol="cmd_check",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_check",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/info.py",
        symbol="cmd_info",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_info",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/inspect_output.py",
        symbol="cmd_inspect_output",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_inspect_output",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/process.py",
        symbol="cmd_process",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_process",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/stage_worker.py",
        symbol="cmd_stage_worker",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_stage_worker",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="model_config",
        reason="Pydantic Settings reads this declarative class configuration during model construction.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="model_post_init",
        reason="Pydantic calls this lifecycle hook after validating each settings instance.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="__context",
        reason="Pydantic supplies this lifecycle-hook argument when it invokes model_post_init.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    *(
        ReviewedSymbol(
            path="backend/app/processing/anime_cleanup.py",
            symbol=symbol,
            reason="This TypedDict field is consumed through keyed profile lookups in the frame filter.",
            evidence_file="backend/tests/test_processing/test_anime_cleanup.py",
            evidence_marker="def test_missing_strengths_use_profile_defaults",
        )
        for symbol in (
            "default_denoise",
            "default_edge_boost",
            "median_size",
            "denoise_gain",
            "edge_radius",
            "edge_gain",
            "edge_threshold",
        )
    ),
)

_FULL_SCAN_ONLY_REVIEWED_SYMBOLS = (
    ReviewedSymbol(
        path="backend/tests/conftest.py",
        symbol="collect_ignore",
        reason="Pytest reads collect_ignore while collecting backend-specific test files.",
        evidence_file="backend/tests/conftest.py",
        evidence_marker="collect_ignore =",
    ),
    *(
        ReviewedSymbol(
            path=path,
            symbol="pytestmark",
            reason="Pytest reads this module marker during collection.",
            evidence_file=path,
            evidence_marker="pytestmark =",
        )
        for path in (
            "backend/tests/test_algorithms/test_interpolation.py",
            "backend/tests/test_algorithms/test_rife_all_models.py",
            "backend/tests/test_algorithms/test_rife_onnx.py",
            "backend/tests/test_algorithms/test_rife_tensorrt.py",
            "backend/tests/test_algorithms/test_tensor_backend_pytorch.py",
            "backend/tests/test_weight_loading.py",
        )
    ),
    ReviewedSymbol(
        path="backend/tests/test_algorithms/test_rife_tensorrt.py",
        symbol="__spec__",
        reason="Importlib reads the synthetic module spec while probing the optional TensorRT module.",
        evidence_file="backend/tests/test_algorithms/test_rife_tensorrt.py",
        evidence_marker="fake_torch_tensorrt.__spec__ =",
    ),
    ReviewedSymbol(
        path="backend/tests/test_integration/test_cli_process_e2e.py",
        symbol="_cleanup_output",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_integration/test_cli_process_e2e.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    ReviewedSymbol(
        path="backend/tests/test_logger.py",
        symbol="restore_root_logger",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_logger.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    ReviewedSymbol(
        path="backend/tests/test_utils/test_dll_paths.py",
        symbol="_reset_registry",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_utils/test_dll_paths.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    *(
        ReviewedSymbol(
            path="scripts/architecture_contracts/python_checks.py",
            symbol=symbol,
            reason="ast.NodeVisitor dispatches this visitor method by node type.",
            evidence_file="scripts/architecture_contracts/python_checks.py",
            evidence_marker="class BoundaryReadVisitor(ast.NodeVisitor)",
        )
        for symbol in (
            "visit_AnnAssign",
            "visit_Assign",
            "visit_AsyncFunctionDef",
            "visit_Attribute",
            "visit_ClassDef",
            "visit_DictComp",
            "visit_For",
            "visit_FunctionDef",
            "visit_GeneratorExp",
            "visit_ListComp",
            "visit_SetComp",
        )
    ),
)


def _validate_reviewed_exclusions() -> None:
    paths = [entry.path for entry in _REVIEWED_EXCLUSIONS]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate Python dead-code exclusion")
    for entry in _REVIEWED_EXCLUSIONS:
        if not entry.reason.strip():
            raise RuntimeError(f"missing reason for Python dead-code exclusion {entry.path}")
        protected = ROOT / entry.path.rstrip("/")
        if entry.path.endswith("/"):
            exists = protected.is_dir()
        else:
            exists = protected.is_file()
        if not exists:
            raise RuntimeError(f"Python dead-code exclusion does not match a protected path: {entry.path}")
        evidence = ROOT / entry.evidence_file
        if not evidence.is_file() or entry.evidence_marker not in evidence.read_text(encoding="utf-8"):
            raise RuntimeError(
                f"Python dead-code exclusion evidence is missing for {entry.path}: "
                f"{entry.evidence_file}::{entry.evidence_marker}"
            )

    expected_rife = {ROOT / path for path in _rife_module_paths()}
    actual_rife = set(_RIFE_PACKAGE.glob("ifnet_v4_*.py"))
    if actual_rife != expected_rife:
        missing = sorted(path.name for path in expected_rife - actual_rife)
        unexpected = sorted(path.name for path in actual_rife - expected_rife)
        raise RuntimeError(
            f"RIFE dynamic-module boundary drifted from the neutral catalog: missing={missing}, unexpected={unexpected}"
        )


def _declared_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.arg):
            symbols.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            symbols.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            symbols.add(node.attr)
    return symbols


def _validate_reviewed_symbols() -> None:
    entries = (*_PRODUCTION_REVIEWED_SYMBOLS, *_FULL_SCAN_ONLY_REVIEWED_SYMBOLS)
    keys = [(entry.path, entry.symbol) for entry in entries]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate path/symbol Python dead-code review")

    declared_by_path: dict[str, set[str]] = {}
    for entry in entries:
        if not entry.reason.strip():
            raise RuntimeError(f"missing reason for Python dead-code symbol {entry.path}::{entry.symbol}")
        source = ROOT / entry.path
        if not source.is_file():
            raise RuntimeError(f"Python dead-code symbol path does not exist: {entry.path}")
        if entry.path not in declared_by_path:
            declared_by_path[entry.path] = _declared_symbols(source)
        symbols = declared_by_path[entry.path]
        if entry.symbol not in symbols:
            raise RuntimeError(f"reviewed Python dead-code symbol is not declared: {entry.path}::{entry.symbol}")
        evidence = ROOT / entry.evidence_file
        if not evidence.is_file() or entry.evidence_marker not in evidence.read_text(encoding="utf-8"):
            raise RuntimeError(
                f"Python dead-code symbol evidence is missing for {entry.path}::{entry.symbol}: "
                f"{entry.evidence_file}::{entry.evidence_marker}"
            )


def literal_handler_targets(path: Path) -> tuple[tuple[str, str], ...]:
    """Read the exact lazy CLI targets from the top-level ``_HANDLERS`` map."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(literal_string_pair_registry(tree, "_HANDLERS").values())


def _validate_handler_symbols(
    handler_path: Path = ROOT / "backend/app/cli/main.py",
    reviewed_symbols: tuple[ReviewedSymbol, ...] = _PRODUCTION_REVIEWED_SYMBOLS,
) -> None:
    """Require exact reviewed command paths and symbols to match ``_HANDLERS``."""
    expected = set(literal_handler_targets(handler_path))
    actual = {
        (entry.path.removeprefix("backend/").removesuffix(".py").replace("/", "."), entry.symbol)
        for entry in reviewed_symbols
        if entry.symbol.startswith("cmd_")
    }
    if actual != expected:
        raise RuntimeError(
            "Vulture CLI handler evidence drifted from _HANDLERS: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )


__all__ = [
    "ROOT",
    "ReviewedExclusion",
    "ReviewedSymbol",
    "_FULL_SCAN_ONLY_REVIEWED_SYMBOLS",
    "_PRODUCTION_REVIEWED_SYMBOLS",
    "_REVIEWED_EXCLUSIONS",
    "_rife_module_paths",
    "_validate_handler_symbols",
    "_validate_reviewed_exclusions",
    "_validate_reviewed_symbols",
    "literal_handler_targets",
]
