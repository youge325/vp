"""Host system probing helpers."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


GPU_VENDOR_KEYWORDS = {
    "nvidia": "nvidia",
    "intel": "intel",
    "amd": "amd",
    "advanced micro devices": "amd",
    "ati": "amd",
}

VIRTUAL_GPU_KEYWORDS = (
    "virtual",
    "remote",
    "mirror",
    "idd",
    "gameviewer",
)


def classify_gpu_vendor(*values: str) -> str:
    """Return a normalized GPU vendor label."""
    haystack = " ".join(value.lower() for value in values if value)
    for keyword, vendor in GPU_VENDOR_KEYWORDS.items():
        if keyword in haystack:
            return vendor
    return "other"


def classify_gpu_device_type(name: str, vendor: str) -> str:
    """Return a normalized GPU device type."""
    lowered = name.lower()
    if any(keyword in lowered for keyword in VIRTUAL_GPU_KEYWORDS):
        return "virtual"
    if vendor == "intel":
        return "integrated"
    if vendor in {"nvidia", "amd"}:
        return "discrete"
    return "other"


def list_gpu_adapters() -> list[dict[str, Any]]:
    """Return normalized GPU adapters for the current host."""
    if sys.platform.startswith("win"):
        return _list_windows_gpu_adapters()
    return []


def _list_windows_gpu_adapters() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,DriverVersion | "
        "ConvertTo-Json -Compress"
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
    adapters: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("Name") or "").strip()
        compatibility = str(row.get("AdapterCompatibility") or "").strip()
        driver_version = str(row.get("DriverVersion") or "").strip()
        vendor = classify_gpu_vendor(name, compatibility)
        device_type = classify_gpu_device_type(name, vendor)
        adapters.append(
            {
                "name": name,
                "vendor": vendor,
                "device_type": device_type,
                "adapter_compatibility": compatibility,
                "driver_version": driver_version,
            }
        )
    return adapters
