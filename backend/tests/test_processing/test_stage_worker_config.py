from __future__ import annotations

import json
from pathlib import Path

from app.planning import ProcessingStep
from app.processing.streaming.stage_worker_config import StageWorkerConfig


def test_stage_worker_config_parses_camel_and_snake_payloads(tmp_path: Path) -> None:
    camel_payload = {
        "stage": {
            "algorithm_type": "super_resolution",
            "algorithm_kwargs": {"scale_factor": 2.0},
            "stage_name": "01_super_resolution",
        },
        "stageIndex": 1,
        "stageTotal": 2,
        "stageName": "01_super_resolution",
        "inputWidth": 320,
        "inputHeight": 180,
        "outputWidth": 640,
        "outputHeight": 360,
        "inputFrameCount": 12,
        "tensorBackendName": "onnx",
        "outputFrameCount": 12,
    }
    config_path = tmp_path / "stage-worker.json"
    config_path.write_text(json.dumps(camel_payload), encoding="utf-8")

    camel_config = StageWorkerConfig.from_json_file(config_path)
    snake_config = StageWorkerConfig.from_mapping(
        {
            "stage": camel_payload["stage"],
            "stage_index": 1,
            "stage_total": 2,
            "stage_name": "01_super_resolution",
            "input_width": 320,
            "input_height": 180,
            "output_width": 640,
            "output_height": 360,
            "input_frame_count": 12,
            "tensor_backend_name": "onnx",
            "output_frame_count": 0,
        }
    )

    assert camel_config.stage == snake_config.stage
    assert camel_config.stage.algorithm_type == "super_resolution"
    assert camel_config.stage.algorithm_kwargs == {"scale_factor": 2.0}
    assert camel_config.output_width == 640
    assert camel_config.output_frame_count == 12
    assert snake_config.output_frame_count is None


def test_stage_worker_config_serializes_existing_processing_step_shape() -> None:
    config = StageWorkerConfig(
        stage=ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        ),
        stage_index=1,
        stage_total=1,
        stage_name="01_frame_interpolation",
        input_width=320,
        input_height=180,
        output_width=320,
        output_height=180,
        input_frame_count=24,
        tensor_backend_name="pytorch",
        output_frame_count=None,
    )

    assert config.to_jsonable() == {
        "stage": {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {"multi": 2},
            "stage_name": "01_frame_interpolation",
        },
        "stageIndex": 1,
        "stageTotal": 1,
        "stageName": "01_frame_interpolation",
        "inputWidth": 320,
        "inputHeight": 180,
        "outputWidth": 320,
        "outputHeight": 180,
        "inputFrameCount": 24,
        "tensorBackendName": "pytorch",
        "outputFrameCount": None,
    }
