"""Real CUDA inference for all packaged Real-RawVSR BasicVSR scales."""

from __future__ import annotations

import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from tests_full_e2e.helpers import (
    BACKEND_DIR,
    assert_completed_process,
    generate_input_video,
    require_python_module,
    run_process,
    run_python_probe,
)


def _config(output_dir: Path, scale_factor: int) -> dict[str, object]:
    return {
        "decode": {"mode": "software", "hwaccel": "", "hwaccelDevice": None, "decoder": "software", "options": {}},
        "workflow": {
            "fpsMode": "multi",
            "processOrder": "super_resolution_then_interpolation",
            "interpolation": {
                "enabled": False,
                "targetFps": 60,
                "multi": 2,
                "algorithm": "rife",
                "model": "4.25",
                "onnxModel": None,
                "scale": 1.0,
                "fp16": False,
                "tensorBackend": "pytorch",
                "engine": "cuda",
            },
            "superResolution": {
                "enabled": True,
                "scaleFactor": float(scale_factor),
                "algorithm": "real-rawvsr-basicvsr",
                "onnxModel": None,
                "tensorBackend": "pytorch",
                "engine": "cuda",
                "numFrames": 10,
            },
            "preprocess": {"enabled": False, "filters": []},
            "postprocess": {"enabled": False, "filters": []},
        },
        "encode": {
            "codec": "libx264",
            "family": "cpu",
            "container": "mp4",
            "keepAudio": True,
            "rateControl": {"mode": "crf", "value": 28},
            "options": {"preset": "ultrafast"},
        },
        "output": {"outputDir": str(output_dir), "openOnComplete": False, "segmentFrames": 1000},
    }


def _probe_streams(path: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["streams"]


@pytest.mark.full_e2e
@pytest.mark.parametrize(("scale_factor", "expected_size"), [(2, (640, 360)), (3, (960, 540)), (4, (1280, 720))])
def test_real_rawvsr_basicvsr_preserves_frames_fps_audio_and_terminal(
    tmp_path: Path,
    scale_factor: int,
    expected_size: tuple[int, int],
) -> None:
    require_python_module("safetensors")
    run_python_probe("import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)")
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / f"output-x{scale_factor}.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    generate_input_video(
        input_path,
        width=320,
        height=180,
        num_frames=5,
        rate=10,
        duration=0.5,
        with_audio=True,
    )

    process = run_process(
        input_path=input_path,
        output_path=output_path,
        config=_config(output_dir, scale_factor),
        extra_env={"VP_RIFE_MODEL_DIR": os.environ.get("VP_RIFE_MODEL_DIR", str(BACKEND_DIR / "models"))},
    )
    completed = assert_completed_process(process, processed_frames=5, output_path=output_path)
    assert completed["outputPath"] == str(output_path)

    streams = _probe_streams(output_path)
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (int(video["width"]), int(video["height"])) == expected_size
    assert int(video["nb_read_frames"]) == 5
    assert Fraction(video["avg_frame_rate"]) == 10
    assert any(stream["codec_type"] == "audio" for stream in streams)
