"""Real PaddleGAN TensorRT task-log e2e.

Run explicitly on machines with Paddle CUDA, Paddle Inference TensorRT, ffmpeg,
and PP-MSVSR weights installed:

    python -m pytest tests_full_e2e/test_paddlegan_tensorrt_task_logs_e2e.py -q -m full_e2e --tb=short
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
    make_paddlegan_process_config,
    probe_output,
    require_paddle_cuda,
    run_process,
)

WEIGHT_ROOT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan"
PPMSVSR_WEIGHT = WEIGHT_ROOT / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
PPMSVSR_AUX_WEIGHT = WEIGHT_ROOT / "_auxiliary" / "modified_spynet_tiny.pdparams"
WIDTH = 128
HEIGHT = 128
NUM_FRAMES = 5


@pytest.mark.full_e2e
def test_paddlegan_tensorrt_engine_logs_reach_parent_process_stderr(tmp_path: Path) -> None:
    require_paddle_cuda()
    assert_nonempty_file(PPMSVSR_WEIGHT, "PP-MSVSR weight")
    assert_nonempty_file(PPMSVSR_AUX_WEIGHT, "PP-MSVSR auxiliary weight")

    input_path = tmp_path / "ppmsvsr-trt-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "ppmsvsr-trt-output.mp4"
    trt_cache_dir = tmp_path / "paddlegan-trt-cache"
    generate_input_video(
        input_path,
        width=WIDTH,
        height=HEIGHT,
        num_frames=NUM_FRAMES,
        rate=25,
        duration=0.2,
    )

    proc = run_process(
        input_path=input_path,
        output_path=output_path,
        config=make_paddlegan_process_config(
            output_dir,
            engine="tensorrt",
            num_frames=NUM_FRAMES,
        ),
        extra_env={"VP_PADDLEGAN_TRT_CACHE_DIR": str(trt_cache_dir)},
    )

    assert_completed_process(proc, processed_frames=NUM_FRAMES, output_path=output_path)
    metadata = probe_output(output_path)
    assert metadata["width"] == WIDTH * 4
    assert metadata["height"] == HEIGHT * 4

    assert "[VP_TRT]" in proc.stderr
    assert re.search(
        r"\d\d:\d\d:\d\d \[INFO\] app\.algorithms\.paddle\.paddlegan_vsr\.runner: "
        r"\[VP_TRT\] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x128x128",
        proc.stderr,
    ) or re.search(
        r"\d\d:\d\d:\d\d \[INFO\] app\.algorithms\.paddle\.paddlegan_vsr\.runner: "
        r"\[VP_TRT\] TensorRT LOAD static_model=",
        proc.stderr,
    )
    assert "[VP_TRT] TensorRT CACHE dir=" in proc.stderr
    assert "[VP_TRT] TensorRT READY outputs=" in proc.stderr
