"""Atomic JSON persistence for resumable segment manifests."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

MANIFEST_VERSION = 2


def load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    """Load a current-version manifest object, returning None for invalid data."""
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return None
    return data


def write_manifest(
    manifest_path: Path,
    *,
    signature: str,
    output_path: Path,
    config_snapshot: dict[str, Any],
) -> None:
    """Persist a manifest through a flushed temporary file and atomic replace."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MANIFEST_VERSION,
        "signature": signature,
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "input_path": str(config_snapshot.get("input_path", "")),
        "output_path": str(output_path),
        "config_snapshot": config_snapshot,
    }
    tmp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(tmp_path, manifest_path)
