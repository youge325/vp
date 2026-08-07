"""Semantic consumers of the neutral application-defaults contract."""

from __future__ import annotations

import ast
import json
import re
import warnings
from pathlib import Path

from contract_codegen.application_defaults import synthesize_application_defaults

from .rules import read_source, relative_path

_REQUIRED_CONSUMERS = {
    "backend/app/config.py": "app.generated.application_defaults",
    "backend/app/cli/defaults.py": "app.generated.application_defaults",
    "backend/app/cli/parser.py": "app.generated.application_defaults",
    "backend/app/benchmark/runner.py": "app.generated.application_defaults",
    "backend/app/catalog/filter_parameters.py": "FILTER_DEFAULTS",
    "frontend/src/services/preset/workflow-defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/enhance-metadata-defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/io-form-rules.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/enhance-read-model.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/enhance-algorithm-defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/filters/filter-catalog.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/filters/anime-cleanup.ts": "APPLICATION_DEFAULTS",
    "frontend/src/components/filter-steps/FilterScale.vue": "APPLICATION_DEFAULTS",
    "frontend/src/components/filter-steps/FilterAnimeCleanup.vue": "APPLICATION_DEFAULTS",
    "frontend/src-tauri/src/runtime/mod.rs": "DEFAULT_RIFE_MODEL_VERSION",
    "scripts/setup-ci-runtime-env.ps1": "runtime-tools.ps1",
    "scripts/prepare-windows-runtime.ps1": "runtime-tools.ps1",
}


def _quoted(value: str) -> str:
    return rf"(?:{re.escape(json.dumps(value))}|{re.escape(repr(value))})"


def _hardcoded_default_patterns(defaults: dict[str, object]) -> dict[str, tuple[re.Pattern[str], ...]]:
    interpolation = defaults["interpolation"]
    super_resolution = defaults["superResolution"]
    workflow = defaults["workflow"]
    output = defaults["output"]
    assert isinstance(interpolation, dict)
    assert isinstance(super_resolution, dict)
    assert isinstance(workflow, dict)
    assert isinstance(output, dict)
    model = str(interpolation["model"])
    segment_frames = int(output["segmentFrames"])
    target_fps = int(interpolation["targetFps"])
    num_frames = int(super_resolution["numFrames"])
    process_order = str(workflow["processOrder"])
    interpolation_algorithm = str(interpolation["algorithm"])
    super_resolution_algorithm = str(super_resolution["algorithm"])
    return {
        "backend/app/config.py": (re.compile(_quoted(model)),),
        "backend/app/cli/defaults.py": (
            re.compile(rf'["\']segmentFrames["\']\s*:\s*{segment_frames}\b'),
            re.compile(rf'["\']numFrames["\']\s*:\s*{num_frames}\b'),
        ),
        "backend/app/cli/parser.py": (
            re.compile(rf"--target-fps[^\n]*default\s*=\s*{target_fps}(?:\.0)?\b"),
            re.compile(_quoted(model)),
        ),
        "backend/app/benchmark/runner.py": (re.compile(_quoted(model)),),
        "frontend/src/services/preset/workflow-defaults.ts": (
            re.compile(_quoted(model)),
            re.compile(rf"targetFps\s*:\s*{target_fps}\b"),
            re.compile(rf"numFrames\s*:\s*{num_frames}\b"),
            re.compile(_quoted(process_order)),
        ),
        "frontend/src/services/preset/enhance-metadata-defaults.ts": (re.compile(_quoted(model)),),
        "frontend/src/services/preset/defaults.ts": (re.compile(rf"segmentFrames\s*:\s*{segment_frames}\b"),),
        "frontend/src/services/preset/io-form-rules.ts": (re.compile(rf":\s*{segment_frames}\b"),),
        "frontend/src/services/preset/enhance-read-model.ts": (re.compile(rf"\?\?\s*{num_frames}\b"),),
        "frontend/src/services/preset/enhance-algorithm-defaults.ts": (
            re.compile(_quoted(interpolation_algorithm)),
            re.compile(_quoted(super_resolution_algorithm)),
        ),
        "frontend/src-tauri/src/runtime/model.rs": (re.compile(_quoted(model)),),
        "scripts/setup-ci-runtime-env.ps1": (re.compile(re.escape(model)),),
        "scripts/prepare-windows-runtime.ps1": (re.compile(re.escape(model)),),
    }


def _filter_default_values(defaults: dict[str, object]) -> dict[str, set[object]]:
    filters = defaults.get("filters")
    if not isinstance(filters, dict):
        return {}
    values: dict[str, set[object]] = {}
    for kind, raw_params in filters.items():
        if kind == "animeCleanup" or not isinstance(raw_params, dict):
            continue
        for name, value in raw_params.items():
            values.setdefault(name, set()).add(value)
    anime = filters.get("animeCleanup")
    if isinstance(anime, dict):
        values.setdefault("profile", set()).add(anime.get("defaultProfile"))
        profiles = anime.get("profiles")
        if isinstance(profiles, dict):
            for strengths in profiles.values():
                if isinstance(strengths, dict):
                    for name, value in strengths.items():
                        values.setdefault(name, set()).add(value)
    return values


def _python_filter_fallback_lines(source: str, defaults: dict[str, set[object]]) -> list[int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError:
        return []
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in defaults.get(node.args[0].value, set())
        ):
            lines.append(node.lineno)
    return lines


def _typescript_filter_fallback_lines(source: str, defaults: dict[str, set[object]]) -> list[int]:
    lines: list[int] = []
    for name, values in defaults.items():
        for value in values:
            literals = [re.escape(str(value))]
            if isinstance(value, str):
                literals = [re.escape(json.dumps(value)), re.escape(repr(value))]
            pattern = re.compile(
                rf"(?:\bparams|\.params)\.{re.escape(name)}\s*\?\?\s*(?:{'|'.join(literals)})(?![\w.])"
            )
            lines.extend(source.count("\n", 0, match.start()) + 1 for match in pattern.finditer(source))
    return lines


def _check_semantic_filter_fallbacks(root: Path, defaults: dict[str, object]) -> list[str]:
    values = _filter_default_values(defaults)
    issues: list[str] = []
    search_specs = (
        (root / "backend/app", {".py"}, _python_filter_fallback_lines),
        (root / "frontend/src", {".ts", ".tsx", ".vue"}, _typescript_filter_fallback_lines),
    )
    for search_root, suffixes, scanner in search_specs:
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes or "generated" in path.parts:
                continue
            source = read_source(path, root)
            for line in scanner(source, values):
                issues.append(
                    f"semantic filter default fallback bypasses generated contract: {relative_path(path, root)}:{line}"
                )
    return issues


def check_application_default_consumers(root: Path) -> list[str]:
    contract_path = root / "contracts/application-defaults.json"
    if not contract_path.is_file():
        return ["missing application defaults contract: contracts/application-defaults.json"]
    model_assets_path = root / "contracts/model-assets.json"
    if not model_assets_path.is_file():
        return ["missing model asset contract: contracts/model-assets.json"]
    defaults = synthesize_application_defaults(
        json.loads(read_source(contract_path, root)),
        json.loads(read_source(model_assets_path, root)),
    )
    patterns = _hardcoded_default_patterns(defaults)
    issues: list[str] = []
    for path_name, marker in _REQUIRED_CONSUMERS.items():
        path = root / path_name
        if not path.is_file():
            issues.append(f"missing application-default consumer: {path_name}")
            continue
        source = read_source(path, root)
        if marker not in source:
            issues.append(f"application-default consumer bypasses generated/shared source: {path_name}")
    for path_name, path_patterns in patterns.items():
        path = root / path_name
        if not path.is_file():
            continue
        source = read_source(path, root)
        for pattern in path_patterns:
            if pattern.search(source):
                issues.append(
                    f"application default is hard-coded instead of generated: "
                    f"{relative_path(path, root)} ({pattern.pattern})"
                )
    issues.extend(_check_semantic_filter_fallbacks(root, defaults))
    return issues
