from __future__ import annotations

import hashlib
import json

from app.planning.processing_steps import ProcessingStep
from app.planning.run_identity import build_run_identity
from app.ports.media import VideoMetadata


def test_run_identity_uses_the_persisted_snapshot_as_signature_source(tmp_path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"video")
    decode_config = {"mode": "software", "options": {"threads": 2}}
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "onnx", "onnx_model": "sr.onnx"},
        stage_name="01_super_resolution",
    )

    identity = build_run_identity(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config={"codec": "libx264"},
        workflow_config={"fpsMode": "multi"},
        output_config={"segmentFrames": 1000, "ignored": True},
        processing_steps=[step],
        video_info=VideoMetadata(
            width=320,
            height=180,
            source_fps=24.0,
            source_frames=5,
            duration=5 / 24,
            has_audio=True,
        ),
    )

    assert identity.config_snapshot == {
        "input_path": str(input_path.resolve()),
        "output_path": str(output_path.resolve()),
        "decode_config": {"mode": "software", "options": {"threads": 2}},
        "encode_config": {"codec": "libx264"},
        "workflow_config": {"fpsMode": "multi"},
        "output_config": {"segmentFrames": 1000},
        "processing_steps": [
            {
                "algorithm_type": "super_resolution",
                "algorithm_kwargs": {
                    "scale_factor": 2.0,
                    "sr_algorithm": "onnx",
                    "onnx_model": "sr.onnx",
                },
                "stage_name": "01_super_resolution",
            }
        ],
        "video_info": {
            "width": 320,
            "height": 180,
            "source_fps": 24.0,
            "source_frames": 5,
        },
    }

    stat = input_path.stat()
    expected_payload = {
        **identity.config_snapshot,
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
    }
    expected_signature = hashlib.sha256(
        json.dumps(expected_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert identity.signature == expected_signature

    decode_config["options"]["threads"] = 8
    assert identity.config_snapshot["decode_config"]["options"]["threads"] == 2
