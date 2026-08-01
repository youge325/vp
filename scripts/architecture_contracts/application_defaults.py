"""Semantic consumers of the neutral application-defaults contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .rules import read_source, relative_path

_REQUIRED_CONSUMERS = {
    "backend/app/config.py": "app.generated.application_defaults",
    "backend/app/cli/defaults.py": "app.generated.application_defaults",
    "backend/app/cli/parser.py": "app.generated.application_defaults",
    "backend/app/benchmark/runner.py": "app.generated.application_defaults",
    "frontend/src/services/preset/workflow-defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/enhance-metadata-defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/defaults.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/io-form-rules.ts": "APPLICATION_DEFAULTS",
    "frontend/src/services/preset/enhance-read-model.ts": "APPLICATION_DEFAULTS",
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
        "frontend/src-tauri/src/runtime/model.rs": (re.compile(_quoted(model)),),
        "scripts/setup-ci-runtime-env.ps1": (re.compile(re.escape(model)),),
        "scripts/prepare-windows-runtime.ps1": (re.compile(re.escape(model)),),
    }


def check_application_default_consumers(root: Path) -> list[str]:
    contract_path = root / "contracts/application-defaults.json"
    if not contract_path.is_file():
        return ["missing application defaults contract: contracts/application-defaults.json"]
    defaults = json.loads(read_source(contract_path, root))
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
    return issues
