"""Real PyTorch RIFE + PaddleGAN VSR CLI e2e.

This file intentionally lives outside ``tests/`` so the default pytest
``testpaths`` does not collect it. Run it explicitly in environments with the
real PyTorch/Paddle runtimes and PaddleGAN weights installed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests_full_e2e.helpers import (
    BACKEND_DIR,
    assert_completed_process,
    assert_nonempty_file,
    generate_input_video,
    json_lines,
    make_paddlegan_process_config,
    probe_output,
    require_python_module,
    run_process,
)

PADDLEGAN_WEIGHT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan" / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
TERMINAL_PROGRESS_FPS_RE = re.compile(r"\|\s+\d+\.\d fps\s+\|")


def _terminal_progress_lines(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.startswith("[VP_PROGRESS]")]


@pytest.mark.full_e2e
def test_cli_process_runs_real_pytorch_interpolation_then_paddlegan_super_resolution(tmp_path: Path) -> None:
    require_python_module("torch")
    require_python_module("paddle")
    assert_nonempty_file(PADDLEGAN_WEIGHT, "PaddleGAN PP-MSVSR weight")

    input_path = tmp_path / "pytorch-paddle-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    generate_input_video(
        input_path,
        width=64,
        height=64,
        num_frames=3,
        rate=30,
        duration=0.1,
    )

    proc = run_process(
        input_path=input_path,
        output_dir=output_dir,
        config=make_paddlegan_process_config(
            output_dir,
            engine="cuda",
            num_frames=8,
            interpolation_enabled=True,
            segment_frames=1000,
        ),
    )

    events = json_lines(proc.stdout)
    progress_stages = {event.get("stage") for event in events if event.get("type") == "progress"}
    assert {"01_frame_interpolation", "02_super_resolution"}.issubset(progress_stages)
    super_resolution_progress = [
        event for event in events if event.get("type") == "progress" and event.get("stage") == "02_super_resolution"
    ]
    assert any(event.get("current") for event in super_resolution_progress), (
        f"No non-zero super-resolution progress event found in stdout:\n{proc.stdout}"
    )
    terminal_progress = _terminal_progress_lines(proc.stderr)
    assert any("[1/2 01_frame_interpolation]" in line for line in terminal_progress), (
        f"No interpolation terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[2/2 02_super_resolution]" in line for line in terminal_progress), (
        f"No super-resolution terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[1/2 01_frame_interpolation]" in line and "100.0%" in line for line in terminal_progress), (
        f"No completed interpolation terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[2/2 02_super_resolution]" in line and "100.0%" in line for line in terminal_progress), (
        f"No completed super-resolution terminal progress line found in stderr:\n{proc.stderr}"
    )
    nonzero_terminal_progress = [line for line in terminal_progress if not re.search(r"\s0/\d+\s", line)]
    assert nonzero_terminal_progress, f"No non-zero terminal progress lines found in stderr:\n{proc.stderr}"
    assert all("--.- fps" not in line for line in nonzero_terminal_progress)
    assert any(TERMINAL_PROGRESS_FPS_RE.search(line) for line in nonzero_terminal_progress)

    completed = assert_completed_process(proc, processed_frames=5)
    output_path = Path(completed["outputPath"])
    metadata = probe_output(output_path)
    assert metadata["width"] == 256
    assert metadata["height"] == 256
