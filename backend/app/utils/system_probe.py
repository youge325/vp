"""Host system probing helpers."""

from __future__ import annotations

import json
import re
import subprocess
import sys

from app.utils.subprocess_utils import hidden_subprocess_kwargs


_GPU_VENDOR_PATTERNS = (
    (re.compile(r"\bnvidia\b", re.IGNORECASE), "nvidia"),
    (re.compile(r"\bintel\b", re.IGNORECASE), "intel"),
    (re.compile(r"\badvanced\s+micro\s+devices\b", re.IGNORECASE), "amd"),
    (re.compile(r"\bamd\b", re.IGNORECASE), "amd"),
    (re.compile(r"\bati\b", re.IGNORECASE), "amd"),
    (re.compile(r"\bhygon\b", re.IGNORECASE), "hygon"),
    (re.compile(r"\bdcu\b", re.IGNORECASE), "hygon"),
)

_VIRTUAL_GPU_NAME_MARKERS = (
    "virtual display",
    "remote display",
    "mirror",
    "idddriver",
    "indirect display",
    "gameviewer",
)

_VIRTUAL_GPU_PNP_PREFIXES = (
    "root\\display\\",
    "indirectdsp\\",
)


def _classify_gpu_vendor(*values: str) -> str:
    """Return a normalized GPU vendor label."""
    haystack = " ".join(value for value in values if value)
    for pattern, vendor in _GPU_VENDOR_PATTERNS:
        if pattern.search(haystack):
            return vendor
    return "other"


def _is_virtual_gpu_adapter(name: str, compatibility: str, pnp_device_id: str) -> bool:
    """Return whether a Windows display controller is a virtual adapter."""
    description = f"{name} {compatibility}".casefold()
    normalized_pnp_id = pnp_device_id.casefold()
    return any(marker in description for marker in _VIRTUAL_GPU_NAME_MARKERS) or normalized_pnp_id.startswith(
        _VIRTUAL_GPU_PNP_PREFIXES
    )


def list_gpu_adapters() -> list[dict[str, str]]:
    """Return normalized GPU adapters for the current host."""
    if sys.platform.startswith("win"):
        return _list_windows_gpu_adapters()
    return []


def _list_windows_gpu_adapters() -> list[dict[str, str]]:
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,PNPDeviceID | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return []

    rows = payload if isinstance(payload, list) else [payload]
    adapters: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        compatibility = str(row.get("AdapterCompatibility") or "").strip()
        pnp_device_id = str(row.get("PNPDeviceID") or "").strip()
        if _is_virtual_gpu_adapter(name, compatibility, pnp_device_id):
            continue
        adapters.append(
            {
                "name": name,
                "vendor": _classify_gpu_vendor(name, compatibility),
            }
        )
    return adapters
