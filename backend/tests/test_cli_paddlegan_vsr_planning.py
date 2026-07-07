import pytest

from app.cli.defaults import _resolve_processing_steps
from app.cli.commands._process_planning import _verify_model_availability, _verify_super_resolution_backend
from app.errors import ProcessError, TaskErrorCode
from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.stage_worker import StageWorkerConfig
from app.processing.streaming.worker_pipeline import build_stage_worker_plans


def _workflow(*, sr_backend="paddle", interpolation_backend="onnx", scale_factor=4.0, algorithm="ppmsvsr"):
    return {
        "interpolation": {
            "enabled": True,
            "tensorBackend": interpolation_backend,
        },
        "superResolution": {
            "enabled": True,
            "scaleFactor": scale_factor,
            "algorithm": algorithm,
            "tensorBackend": sr_backend,
            "autoDownloadWeights": True,
        },
    }


def test_paddlegan_vsr_requires_4x_scale_factor():
    with pytest.raises(ProcessError) as exc_info:
        _verify_super_resolution_backend(_workflow(scale_factor=2.0), "onnx")

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "4x" in exc_info.value.message


def test_paddlegan_vsr_allows_pytorch_interpolation_plus_paddle_super_resolution():
    _verify_super_resolution_backend(_workflow(interpolation_backend="pytorch"), "pytorch")


def test_paddlegan_vsr_rejects_paddle_interpolation_backend_combination():
    with pytest.raises(ProcessError) as exc_info:
        _verify_super_resolution_backend(_workflow(interpolation_backend="paddle"), "paddle")

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "RIFE" in exc_info.value.message
    assert "Paddle" in exc_info.value.message


def test_restored_paddlegan_vsr_models_are_accepted_by_backend_planning():
    for algorithm in ["ppmsvsr-large", "basicvsr", "iconvsr", "basicvsr-plus-plus"]:
        _verify_super_resolution_backend(_workflow(algorithm=algorithm), "onnx")


def test_paddlegan_vsr_missing_auxiliary_weight_is_rejected_before_stage_worker(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    main_weight = tmp_path / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
    main_weight.parent.mkdir(parents=True)
    main_weight.write_bytes(b"main")
    monkeypatch.setattr(weights, "fixed_weight_root", lambda: tmp_path)
    workflow = {
        "interpolation": {"enabled": False, "model": "4.25"},
        "superResolution": {
            "enabled": True,
            "algorithm": "ppmsvsr",
            "tensorBackend": "paddle",
            "autoDownloadWeights": True,
        },
    }
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr", "tensor_backend": "paddle"},
            stage_name="01_super_resolution",
        )
    ]

    with pytest.raises(ProcessError) as exc_info:
        _verify_model_availability(workflow, steps, "paddle")

    expected_aux = tmp_path / "_auxiliary" / "modified_spynet_tiny.pdparams"
    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(expected_aux) in exc_info.value.message


def test_paddlegan_vsr_allows_onnx_interpolation_plus_paddle_super_resolution():
    _verify_super_resolution_backend(_workflow(), "onnx")


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
            "engine": "cuda",
            "numFrames": 8,
            "autoDownloadWeights": True,
        },
        "anime": {"enabled": False, "profile": "clean-lines", "denoise": 10, "edgeBoost": 15},
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }

    steps = _resolve_processing_steps(workflow)

    assert len(steps) == 1
    assert steps[0].algorithm_type == "super_resolution"
    assert steps[0].algorithm_kwargs == {
        "scale_factor": 4.0,
        "sr_algorithm": "ppmsvsr",
        "onnx_model": None,
        "engine": "cuda",
        "tensor_backend": "paddle",
        "num_frames": 8,
    }
    assert "auto_download_weights" not in steps[0].algorithm_kwargs


def test_pytorch_interpolation_plus_paddlegan_super_resolution_builds_isolated_stage_backends():
    workflow = {
        "fpsMode": "multi",
        "processOrder": "frame_interpolation_then_super_resolution",
        "interpolation": {
            "enabled": True,
            "targetFps": 60,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "pytorch",
        },
        "superResolution": {
            "enabled": True,
            "scaleFactor": 4.0,
            "algorithm": "ppmsvsr",
            "tensorBackend": "paddle",
            "engine": "cuda",
            "numFrames": 8,
            "autoDownloadWeights": False,
        },
        "anime": {"enabled": False, "profile": "clean-lines", "denoise": 10, "edgeBoost": 15},
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }

    steps = _resolve_processing_steps(workflow)
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)
    worker_plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="pytorch",
        source_width=64,
        source_height=64,
        source_frame_count=3,
    )

    assert [step.algorithm_type for step in steps] == ["frame_interpolation", "super_resolution"]
    assert "tensor_backend" not in steps[0].algorithm_kwargs
    assert steps[1].algorithm_kwargs["tensor_backend"] == "paddle"
    assert [plan.config.tensor_backend_name for plan in worker_plans] == ["pytorch", "paddle"]
    assert [plan.output_frame_count for plan in worker_plans] == [5, 5]
    assert (worker_plans[-1].config.output_width, worker_plans[-1].config.output_height) == (256, 256)
    assert worker_plans[-1].config.stage.algorithm_kwargs["num_frames"] == 8


def test_paddlegan_num_frames_survives_stage_worker_config_roundtrip():
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
    stage_plan = build_stage_plan([step], 12, source_duration=1.0, output_fps=None)
    worker_plan = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="paddle",
        source_width=64,
        source_height=64,
        source_frame_count=12,
    )[0]

    parsed = StageWorkerConfig.from_mapping(worker_plan.config.to_jsonable())

    assert parsed.stage.algorithm_kwargs["num_frames"] == 5
