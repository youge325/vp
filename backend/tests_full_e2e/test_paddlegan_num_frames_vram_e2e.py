"""Real PP-MSVSR numFrames + VRAM e2e.

This file intentionally lives outside ``tests/`` so default pytest does not
collect it. Run explicitly on machines with Paddle CUDA and real PP-MSVSR
weights installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.utils.model_metrics import get_paddlegan_model_detail
from tests_full_e2e.helpers import (
    BACKEND_DIR,
    assert_completed_process,
    assert_nonempty_file,
    generate_input_video,
    make_paddlegan_process_config,
    probe_output,
    require_paddle_cuda,
    require_python_module,
    run_process,
    trace_lines,
)

PADDLEGAN_WEIGHT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan" / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
WIDTH = 640
HEIGHT = 288
NUM_FRAMES = 5


def _expected_ppmsvsr_vram_bytes() -> float:
    metrics = get_paddlegan_model_detail("ppmsvsr")["metrics"]
    return (
        metrics["runtimeOverheadBytes"]
        + metrics["parameterBytes"]
        + metrics["activationBytesPerMegapixel"] * (WIDTH * HEIGHT / 1_000_000.0) * NUM_FRAMES
    )


@pytest.mark.full_e2e
def test_ppmsvsr_num_frames_reaches_runner_and_reserved_vram_matches_estimate(tmp_path: Path) -> None:
    require_python_module("paddle")
    require_paddle_cuda()
    assert_nonempty_file(PADDLEGAN_WEIGHT, "PaddleGAN PP-MSVSR weight")

    input_path = tmp_path / "ppmsvsr-nf5-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "ppmsvsr-nf5-output.mp4"
    trace_path = tmp_path / "paddlegan-trace.jsonl"
    generate_input_video(
        input_path,
        width=WIDTH,
        height=HEIGHT,
        num_frames=NUM_FRAMES,
        rate=27,
        duration=0.2,
    )

    proc = run_process(
        input_path=input_path,
        output_path=output_path,
        config=make_paddlegan_process_config(
            output_dir,
            engine="cuda",
            num_frames=NUM_FRAMES,
        ),
        extra_env={"VP_PADDLEGAN_VSR_TRACE_PATH": str(trace_path)},
    )

    assert_completed_process(proc, processed_frames=NUM_FRAMES, output_path=output_path)
    metadata = probe_output(output_path)
    assert metadata["width"] == WIDTH * 4
    assert metadata["height"] == HEIGHT * 4

    trace = trace_lines(trace_path)[-1]
    assert trace["modelId"] == "ppmsvsr"
    assert trace["configuredNumFrames"] == NUM_FRAMES
    assert trace["inputFrameCount"] == NUM_FRAMES
    assert [chunk["chunkFrameCount"] for chunk in trace["chunks"]] == [NUM_FRAMES]
    assert trace["chunks"][0]["inputShape"] == [1, NUM_FRAMES, 3, HEIGHT, WIDTH]
    assert trace["chunks"][0]["outputShape"] == [1, NUM_FRAMES, 3, HEIGHT * 4, WIDTH * 4]

    reserved = trace["maxMemoryReservedBytes"]
    allocated = trace["maxMemoryAllocatedBytes"]
    expected = _expected_ppmsvsr_vram_bytes()
    assert reserved > 0
    assert allocated > 0
    assert expected * 0.75 <= reserved <= expected * 1.10
