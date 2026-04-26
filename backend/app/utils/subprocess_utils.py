"""Subprocess helpers shared by backend runtime wrappers."""

from __future__ import annotations

import subprocess
import sys


def hidden_subprocess_kwargs() -> dict[str, int]:
    """Return kwargs that keep Windows console subprocesses hidden."""
    if sys.platform.startswith("win") and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
