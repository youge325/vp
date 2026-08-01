"""External command invocation shared by language generators."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise RuntimeError(f"contract generator failed ({completed.returncode}): {' '.join(command)}")
