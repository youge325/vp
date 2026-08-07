"""Semantic consumers and literal-drift checks for model assets."""

from __future__ import annotations

import json
from pathlib import Path

from .rules import read_source, relative_path

_REQUIRED_MODEL_ASSET_CONSUMERS = {
    "backend/app/algorithms/pytorch/real_rawvsr/assets.py": "app.generated.model_assets",
    "backend/app/catalog/algorithm_capabilities.py": "app.generated.model_assets",
    "frontend/src-tauri/src/runtime/model.rs": "REAL_RAWVSR_MODEL_FAMILIES",
    "scripts/runtime-tools.ps1": "contracts\\model-assets.json",
    "scripts/prepare_real_rawvsr_models.py": "contracts/model-assets.json",
    ".github/workflows/release.yml": "prepare_real_rawvsr_models.py",
}

_SCAN_ROOTS = ("backend/app", "frontend/src", "frontend/src-tauri/src", "scripts", ".github/workflows")
_SCAN_SUFFIXES = {".py", ".rs", ".ts", ".vue", ".ps1", ".yml", ".yaml"}
_LITERAL_ALLOWLIST = {
    "backend/app/generated/model_assets.py",
    "backend/app/generated/stage_worker_contracts.py",
    "frontend/src-tauri/src/generated/model_assets.rs",
}


def check_model_asset_consumers(root: Path) -> list[str]:
    contract_path = root / "contracts/model-assets.json"
    if not contract_path.is_file():
        return ["missing model asset contract: contracts/model-assets.json"]
    assets = json.loads(read_source(contract_path, root))
    issues: list[str] = []
    for path_name, marker in _REQUIRED_MODEL_ASSET_CONSUMERS.items():
        path = root / path_name
        if not path.is_file():
            issues.append(f"missing model-asset consumer: {path_name}")
        elif marker not in read_source(path, root):
            issues.append(f"model-asset consumer bypasses neutral manifest: {path_name}")

    protected_literals = {
        str(variant[field])
        for family in assets["families"]
        for variant in family["variants"]
        for field in ("googleDriveFileId", "sourceSha256", "inferenceSha256")
    }
    algorithm_ids = {str(family["algorithmId"]) for family in assets["families"]}
    for scan_root_name in _SCAN_ROOTS:
        scan_root = root / scan_root_name
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or path.suffix not in _SCAN_SUFFIXES:
                continue
            path_name = relative_path(path, root)
            if path_name in _LITERAL_ALLOWLIST:
                continue
            source = read_source(path, root)
            if algorithm_ids and all(algorithm_id in source for algorithm_id in algorithm_ids):
                issues.append(f"complete model algorithm inventory is mirrored outside generated bindings: {path_name}")
                continue
            for literal in protected_literals:
                if literal in source:
                    issues.append(f"model asset literal is mirrored outside generated bindings: {path_name}")
                    break
    return issues
