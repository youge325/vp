import json

import pytest

from app.adapters.model_availability import LocalModelAvailability
from app.config import settings
from app.errors import ProcessError, TaskErrorCode
from app.planning import (
    ProcessingStep,
    StageProjection,
    build_stage_plan,
    validate_workflow_requirements,
)
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.worker_plans import build_stage_worker_plans


def _super_resolution_step(
    *,
    backend: str = "paddle",
    scale_factor: float = 4.0,
    algorithm: str = "ppmsvsr",
) -> ProcessingStep:
    return ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": scale_factor,
            "sr_algorithm": algorithm,
            "onnx_model": None,
            "tensor_backend": backend,
        },
        stage_name="01_super_resolution",
    )


def _validate(steps: list[ProcessingStep]) -> None:
    validate_workflow_requirements(steps, LocalModelAvailability(settings.RIFE_MODEL_DIR))


def test_planning_uses_an_injected_model_availability_port():
    validated: list[ProcessingStep] = []

    class _Availability:
        def validate(self, step: ProcessingStep) -> None:
            validated.append(step)

    step = _super_resolution_step(backend="onnx", algorithm="external-onnx")
    validate_workflow_requirements([step], _Availability())

    assert validated == [step]
    assert step.descriptor.factory_key == "onnx_super_resolution"


def test_paddlegan_vsr_requires_4x_scale_factor():
    with pytest.raises(ProcessError) as exc_info:
        _validate([_super_resolution_step(scale_factor=2.0)])

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "4x" in exc_info.value.message


def test_paddlegan_vsr_rejects_paddle_interpolation_backend_combination():
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={
            "algorithm": "rife",
            "model_version": "4.25",
            "tensor_backend": "paddle",
        },
        stage_name="01_frame_interpolation",
    )

    with pytest.raises(ProcessError) as exc_info:
        _validate([step])

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "RIFE" in exc_info.value.message
    assert "Paddle" in exc_info.value.message


def test_restored_paddlegan_vsr_models_are_accepted_by_backend_planning(monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    monkeypatch.setattr(weights, "ensure_paddlegan_vsr_weights", lambda _algorithm: None)
    for algorithm in ["ppmsvsr-large", "basicvsr", "iconvsr", "basicvsr-plus-plus"]:
        _validate([_super_resolution_step(algorithm=algorithm)])


def test_paddlegan_vsr_missing_auxiliary_weight_is_rejected_before_stage_worker(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    main_weight = tmp_path / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
    main_weight.parent.mkdir(parents=True)
    main_weight.write_bytes(b"main")
    monkeypatch.setattr(weights, "_fixed_weight_root", lambda: tmp_path)
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 4.0,
                "sr_algorithm": "ppmsvsr",
                "tensor_backend": "paddle",
            },
            stage_name="01_super_resolution",
        )
    ]

    with pytest.raises(ProcessError) as exc_info:
        _validate(steps)

    expected_aux = tmp_path / "_auxiliary" / "modified_spynet_tiny.pdparams"
    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(expected_aux) in exc_info.value.message


def test_onnx_super_resolution_model_is_checked_from_its_stage_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(tmp_path))
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "sr_algorithm": "real-esrgan",
                "onnx_model": None,
                "tensor_backend": "onnx",
            },
            stage_name="01_super_resolution",
        )
    ]

    with pytest.raises(ProcessError) as exc_info:
        _validate(steps)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert exc_info.value.details["tensor_backend"] == "onnx"
    assert exc_info.value.details["stage"] == "01_super_resolution"


def test_mixed_pytorch_interpolation_and_onnx_sr_checks_both_stage_models(tmp_path, monkeypatch):
    model_path = tmp_path / "flownet_v4.25.pkl"
    model_path.write_bytes(b"rife")
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(tmp_path))
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={
                "algorithm": "rife",
                "model_version": "4.25",
                "tensor_backend": "pytorch",
            },
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "sr_algorithm": "real-esrgan",
                "onnx_model": None,
                "tensor_backend": "onnx",
            },
            stage_name="02_super_resolution",
        ),
    ]

    with pytest.raises(ProcessError) as exc_info:
        _validate(steps)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert exc_info.value.details["stage"] == "02_super_resolution"


def test_rife_paddle_backend_is_rejected_in_planning():
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={
                "algorithm": "rife",
                "model_version": "4.25",
                "tensor_backend": "paddle",
            },
            stage_name="01_frame_interpolation",
        )
    ]

    with pytest.raises(ProcessError) as exc_info:
        _validate(steps)

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert exc_info.value.details["tensor_backend"] == "paddle"


def test_paddlegan_vsr_step_carries_super_resolution_runtime_fields():
    workflow = {
        "fpsMode": "multi",
        "processOrder": "super_resolution_then_interpolation",
        "interpolation": {
            "enabled": False,
            "targetFps": 60,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "onnx",
        },
        "superResolution": {
            "enabled": True,
            "scaleFactor": 4.0,
            "algorithm": "ppmsvsr",
            "tensorBackend": "paddle",
            "engine": "tensorrt",
            "numFrames": 8,
        },
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }

    projection = StageProjection.from_workflow(workflow)
    steps = projection.steps

    assert len(steps) == 1
    assert steps[0].algorithm_type == "super_resolution"
    assert steps[0].algorithm_kwargs == {
        "scale_factor": 4.0,
        "sr_algorithm": "ppmsvsr",
        "onnx_model": None,
        "engine": "tensorrt",
        "tensor_backend": "paddle",
        "num_frames": 8,
    }
    stage_plan = build_stage_plan(projection, 12, source_duration=1.0, output_fps=None)
    worker_plan = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_width=64,
        source_height=64,
        source_frame_count=12,
    )[0]
    assert worker_plan.config.stage.algorithm_kwargs["engine"] == "tensorrt"


def test_pytorch_interpolation_plus_paddlegan_super_resolution_builds_isolated_stage_backends():
    workflow = {
        "fpsMode": "multi",
        "processOrder": "frame_interpolation_then_super_resolution",
        "interpolation": {
            "enabled": True,
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
            "scaleFactor": 4.0,
            "algorithm": "ppmsvsr",
            "tensorBackend": "paddle",
            "engine": "cuda",
            "numFrames": 8,
        },
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }

    projection = StageProjection.from_workflow(workflow)
    steps = projection.steps
    stage_plan = build_stage_plan(projection, 3, source_duration=1.0, output_fps=None)
    worker_plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_width=64,
        source_height=64,
        source_frame_count=3,
    )

    assert [step.algorithm_type for step in steps] == ["frame_interpolation", "super_resolution"]
    assert steps[0].algorithm_kwargs["tensor_backend"] == "pytorch"
    assert steps[1].algorithm_kwargs["tensor_backend"] == "paddle"
    assert [plan.config.tensor_backend_name for plan in worker_plans] == ["pytorch", "paddle"]
    assert [plan.output_frame_count for plan in worker_plans] == [5, 5]
    assert (worker_plans[-1].config.output_width, worker_plans[-1].config.output_height) == (256, 256)
    assert worker_plans[-1].config.stage.algorithm_kwargs["num_frames"] == 8


def test_paddlegan_num_frames_survives_stage_worker_config_roundtrip(tmp_path):
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 4.0,
            "sr_algorithm": "ppmsvsr",
            "tensor_backend": "paddle",
            "num_frames": 5,
        },
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan(StageProjection((step,)), 12, source_duration=1.0, output_fps=None)
    worker_plan = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_width=64,
        source_height=64,
        source_frame_count=12,
    )[0]

    config_path = tmp_path / "stage-worker.json"
    config_path.write_text(json.dumps(worker_plan.config.to_jsonable()), encoding="utf-8")
    parsed = StageWorkerConfig.from_json_file(config_path)

    assert parsed.stage.algorithm_kwargs["num_frames"] == 5
