from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.generated.stage_worker_contracts import StageWorkerConfig
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.stage_worker_config import (
    build_stage_worker_step,
    load_stage_worker_config,
    processing_step_from_config,
)


def _interpolation_worker_config(
    *, frame_count: int, output_frame_count: int, dimensions: tuple[int, int]
) -> StageWorkerConfig:
    width, height = dimensions
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={
            "multi": 2,
            "algorithm": "rife",
            "model_version": "4.25",
            "scale": 1.0,
            "fp16": False,
            "onnx_model": None,
            "engine": "cuda",
        },
        stage_name="01_frame_interpolation",
    )
    return StageWorkerConfig(
        stage=build_stage_worker_step(step),
        stage_index=1,
        stage_total=1,
        stage_name=step.stage_name,
        input_width=width,
        input_height=height,
        output_width=width,
        output_height=height,
        input_frame_count=frame_count,
        tensor_backend_name="pytorch",
        output_frame_count=output_frame_count,
    )


def test_stage_worker_config_parses_canonical_camel_payload(tmp_path: Path) -> None:
    camel_payload = {
        "stage": {
            "algorithm_type": "super_resolution",
            "algorithm_kwargs": {
                "sr_algorithm": "placeholder",
                "onnx_model": None,
                "engine": "cuda",
            },
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
    camel_config = load_stage_worker_config(config_path)

    assert camel_config.stage.algorithm_type == "super_resolution"
    assert camel_config.stage.algorithm_kwargs.model_dump(exclude_unset=True) == {
        "sr_algorithm": "placeholder",
        "onnx_model": None,
        "engine": "cuda",
    }
    assert camel_config.output_width == 640
    assert camel_config.output_frame_count == 12


def test_stage_worker_wire_rejects_python_field_names(tmp_path: Path) -> None:
    payload = {
        "stage": {
            "algorithm_type": "frame_filter_chain",
            "algorithm_kwargs": {"filters": []},
        },
        "stage_index": 1,
        "stageTotal": 1,
        "stageName": "01_frame_filter_chain",
        "inputWidth": 1,
        "inputHeight": 1,
        "outputWidth": 1,
        "outputHeight": 1,
        "inputFrameCount": 1,
        "tensorBackendName": None,
        "outputFrameCount": 1,
    }
    config_path = tmp_path / "snake-worker.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="stageIndex"):
        load_stage_worker_config(config_path)


def test_stage_worker_config_serializes_existing_processing_step_shape() -> None:
    config = _interpolation_worker_config(frame_count=24, output_frame_count=47, dimensions=(320, 180))

    assert config.model_dump(by_alias=True, mode="json", exclude_unset=True) == {
        "stage": {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {
                "multi": 2,
                "model_version": "4.25",
                "scale": 1.0,
                "fp16": False,
                "onnx_model": None,
                "engine": "cuda",
            },
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
        "outputFrameCount": 47,
    }


def test_stage_worker_config_rejects_unknown_algorithm_type(tmp_path: Path) -> None:
    config_path = tmp_path / "stage-worker.json"
    config_path.write_text(
        json.dumps(
            {
                "stage": {
                    "algorithm_type": "unknown_stage",
                    "algorithm_kwargs": {},
                },
                "stageIndex": 1,
                "stageTotal": 1,
                "stageName": "01_unknown_stage",
                "inputWidth": 320,
                "inputHeight": 180,
                "outputWidth": 320,
                "outputHeight": 180,
                "inputFrameCount": 12,
                "tensorBackendName": "pytorch",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validation error"):
        load_stage_worker_config(config_path)


def test_generated_config_converts_to_domain_step_once() -> None:
    config = _interpolation_worker_config(frame_count=2, output_frame_count=3, dimensions=(1, 1))

    step = processing_step_from_config(config)

    assert step.algorithm_type == "frame_interpolation"
    assert step.execution_mode == "pair"


@pytest.mark.parametrize(
    "algorithm_kwargs",
    [
        {"multi": True},
        {"sr_algorithm": "ppmsvsr", "num_frames": True},
        {"sr_algorithm": "ppmsvsr", "unexpected": 1},
    ],
)
def test_generated_worker_kwargs_reject_bool_integers_and_extra_fields(algorithm_kwargs) -> None:
    algorithm_type = "frame_interpolation" if "multi" in algorithm_kwargs else "super_resolution"

    with pytest.raises(ValueError, match="validation error"):
        StageWorkerConfig.model_validate(
            {
                "stage": {
                    "algorithm_type": algorithm_type,
                    "algorithm_kwargs": algorithm_kwargs,
                },
                "stageIndex": 1,
                "stageTotal": 1,
                "stageName": "01_stage",
                "inputWidth": 1,
                "inputHeight": 1,
                "outputWidth": 1,
                "outputHeight": 1,
                "inputFrameCount": 1,
                "tensorBackendName": "onnx",
                "outputFrameCount": 1,
            }
        )


def test_generated_worker_step_rejects_discriminant_kwargs_mismatch_before_write() -> None:
    payload = {
        "stage": {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {
                "scale_factor": 2.0,
                "sr_algorithm": "placeholder",
                "onnx_model": "sr.onnx",
                "engine": "cuda",
            },
        },
        "stageIndex": 1,
        "stageTotal": 1,
        "stageName": "01_stage",
        "inputWidth": 1,
        "inputHeight": 1,
        "outputWidth": 2,
        "outputHeight": 2,
        "inputFrameCount": 1,
        "tensorBackendName": "onnx",
        "outputFrameCount": 1,
    }

    with pytest.raises(ValueError, match="validation error"):
        StageWorkerConfig.model_validate(payload)


@pytest.mark.parametrize(
    "filter_step",
    [
        {"kind": "scale", "enabled": True, "params": {"width": 2, "unexpected": 1}},
        {"kind": "scale", "enabled": True, "params": {"width": True}},
        {"kind": "crop", "enabled": True, "params": {"x": -1}},
    ],
)
def test_generated_worker_filter_protocol_rejects_unknown_bool_and_negative_values(filter_step) -> None:
    payload = {
        "stage": {
            "algorithm_type": "frame_filter_chain",
            "algorithm_kwargs": {"filters": [filter_step]},
        },
        "stageIndex": 1,
        "stageTotal": 1,
        "stageName": "01_frame_filter_chain",
        "inputWidth": 1,
        "inputHeight": 1,
        "outputWidth": 1,
        "outputHeight": 1,
        "inputFrameCount": 1,
        "tensorBackendName": None,
        "outputFrameCount": 1,
    }

    with pytest.raises(ValueError, match="validation error"):
        StageWorkerConfig.model_validate(payload)


def test_worker_step_uses_top_level_backend_as_the_only_backend_source() -> None:
    domain_step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "sr_algorithm": "ppmsvsr",
            "scale_factor": 4.0,
            "tensor_backend": "paddle",
            "onnx_model": None,
            "engine": "cuda",
            "num_frames": 10,
        },
        stage_name="01_super_resolution",
    )
    wire_step = build_stage_worker_step(domain_step)
    assert "tensor_backend" not in wire_step.algorithm_kwargs.model_dump(exclude_unset=True)

    config = StageWorkerConfig(
        stage=wire_step,
        stage_index=1,
        stage_total=1,
        stage_name=domain_step.stage_name,
        input_width=1,
        input_height=1,
        output_width=4,
        output_height=4,
        input_frame_count=1,
        tensor_backend_name="paddle",
        output_frame_count=1,
    )
    restored = processing_step_from_config(config)
    assert restored.algorithm_kwargs["tensor_backend"] == "paddle"


def test_stage_worker_config_rejects_cross_field_mismatch(tmp_path: Path) -> None:
    payload = {
        "stage": {
            "algorithm_type": "frame_filter_chain",
            "algorithm_kwargs": {"filters": []},
        },
        "stageIndex": 2,
        "stageTotal": 1,
        "stageName": "wrong-name",
        "inputWidth": 1,
        "inputHeight": 1,
        "outputWidth": 1,
        "outputHeight": 1,
        "inputFrameCount": 1,
        "tensorBackendName": "onnx",
        "outputFrameCount": 1,
    }
    config_path = tmp_path / "invalid-worker.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="stageIndex"):
        load_stage_worker_config(config_path)


@pytest.mark.parametrize(
    ("step", "backend"),
    [
        (
            ProcessingStep(
                algorithm_type="frame_interpolation",
                algorithm_kwargs={
                    "multi": 2,
                    "model_version": "4.25",
                    "scale": 1.0,
                    "fp16": False,
                    "onnx_model": None,
                    "engine": "cuda",
                },
                stage_name="01_frame_interpolation",
            ),
            "paddle",
        ),
        (
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={
                    "sr_algorithm": "placeholder",
                    "onnx_model": "sr.onnx",
                    "engine": "cuda",
                },
                stage_name="01_super_resolution",
            ),
            "pytorch",
        ),
    ],
)
def test_stage_worker_config_rejects_backend_variant_mismatch(step: ProcessingStep, backend: str) -> None:
    config = StageWorkerConfig(
        stage=build_stage_worker_step(step),
        stage_index=1,
        stage_total=1,
        stage_name=step.stage_name,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        input_frame_count=1,
        tensor_backend_name=backend,
        output_frame_count=1,
    )

    with pytest.raises(ValueError, match="does not support backend"):
        processing_step_from_config(config)
