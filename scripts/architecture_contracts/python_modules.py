"""Shared Python module-name primitives for repository static analysis."""

from __future__ import annotations

from pathlib import Path


def python_module_name(package_root: Path, path: Path) -> str:
    """Resolve a source path to its import name, including the package root."""
    parts = list(path.relative_to(package_root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


__all__ = ["python_module_name"]
