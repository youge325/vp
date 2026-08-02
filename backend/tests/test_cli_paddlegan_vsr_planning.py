import sys
from types import SimpleNamespace

import pytest

from app.adapters.model_availability import LocalModelAvailability
from app.config import settings
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.planning.workflow_validation import validate_workflow_requirements
from app.processing.streaming.stage_worker_config import load_stage_worker_config
from app.processing.streaming.worker_plans import build_stage_worker_plans
from tests.support.video_metadata import make_video_metadata


class _UnexpectedAvailability:
    def validate(self, _step: ProcessingStep) -> None:
        raise AssertionError("model availability must not run for an invalid descriptor")


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
            "engine": "cuda",
            "num_frames": 5 if algorithm == "edvr" else 10,
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
            "engine": "cuda",
        },
        stage_name="01_frame_interpolation",
    )

    with pytest.raises(ProcessError) as exc_info:
        _validate([step])

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "RIFE" in exc_info.value.message
    assert "Paddle" in exc_info.value.message


def test_planning_rejects_unknown_rife_version_before_model_probe() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={
            "algorithm": "rife",
            "model_version": "99.0",
            "tensor_backend": "pytorch",
            "engine": "cuda",
        },
        stage_name="01_frame_interpolation",
    )

    with pytest.raises(ProcessError, match="Unsupported RIFE model version"):
        validate_workflow_requirements([step], _UnexpectedAvailability())


def test_edvr_rejects_noncanonical_fixed_window_before_model_probe() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 4.0,
            "sr_algorithm": "edvr",
            "num_frames": 7,
            "tensor_backend": "paddle",
            "engine": "cuda",
        },
        stage_name="01_super_resolution",
    )

    with pytest.raises(ProcessError, match="fixed 5-frame window"):
        validate_workflow_requirements([step], _UnexpectedAvailability())


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
                "engine": "cuda",
                "num_frames": 10,
            },
            stage_name="01_super_resolution",
        )
    ]

    with pytest.raises(ProcessError) as exc_info:
        _validate(steps)

    expected_aux = tmp_path / "_auxiliary" / "modified_spynet_tiny.pdparams"
    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(expected_aux) in exc_info.value.message


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (FileNotFoundError("BasicVSR x2 model weight is missing"), "missing"),
        (RuntimeError("BasicVSR x2 model weight SHA-256 mismatch"), "SHA-256 mismatch"),
    ],
)
def test_real_rawvsr_missing_or_corrupt_weight_is_a_typed_model_error(monkeypatch, failure, message):
    from app.algorithms.pytorch.real_rawvsr_basicvsr import assets

    def fail_model_probe(_model_root, _scale_factor):
        raise failure

    monkeypatch.setattr(assets, "ensure_model_asset", fail_model_probe)
    step = _super_resolution_step(backend="pytorch", scale_factor=2.0, algorithm="real-rawvsr-basicvsr")

    with pytest.raises(ProcessError) as exc_info:
        _validate([step])

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert message in exc_info.value.message
    assert exc_info.value.details["scale_factor"] == 2


def test_real_rawvsr_requires_available_cuda_after_model_validation(tmp_path, monkeypatch):
    from app.algorithms.pytorch.real_rawvsr_basicvsr import assets

    model_path = tmp_path / "model.safetensors"
    model_path.write_bytes(b"safe")
    monkeypatch.setattr(assets, "ensure_model_asset", lambda _root, _scale: model_path)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    step = _super_resolution_step(backend="pytorch", scale_factor=2.0, algorithm="real-rawvsr-basicvsr")

    with pytest.raises(ProcessError) as exc_info:
        _validate([step])

    assert exc_info.value.code == TaskErrorCode.MISSING_TENSOR_BACKEND
    assert "NVIDIA CUDA" in exc_info.value.message


def test_onnx_super_resolution_model_is_checked_from_its_stage_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(tmp_path))
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "sr_algorithm": "real-esrgan",
                "onnx_model": None,
                "tensor_backend": "onnx",
                "engine": "cuda",
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
                "engine": "cuda",
            },
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "sr_algorithm": "real-esrgan",
                "onnx_model": None,
                "tensor_backend": "onnx",
                "engine": "cuda",
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
                "engine": "cuda",
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
    stage_plan = build_stage_plan(
        projection,
        make_video_metadata(12, duration=1.0, width=64, height=64),
        output_fps=None,
    )
    worker_config = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_frame_count=12,
    )[0]
    assert worker_config.stage.algorithm_kwargs.engine == "tensorrt"


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
    stage_plan = build_stage_plan(
        projection,
        make_video_metadata(3, duration=1.0, width=64, height=64),
        output_fps=None,
    )
    worker_configs = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_frame_count=3,
    )

    assert [step.algorithm_type for step in steps] == ["frame_interpolation", "super_resolution"]
    assert steps[0].algorithm_kwargs["tensor_backend"] == "pytorch"
    assert steps[1].algorithm_kwargs["tensor_backend"] == "paddle"
    assert [config.tensor_backend_name for config in worker_configs] == ["pytorch", "paddle"]
    assert [config.output_frame_count for config in worker_configs] == [5, 5]
    assert (worker_configs[-1].output_width, worker_configs[-1].output_height) == (256, 256)
    assert worker_configs[-1].stage.algorithm_kwargs.num_frames == 8


def test_paddlegan_num_frames_survives_stage_worker_config_roundtrip(tmp_path):
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 4.0,
            "sr_algorithm": "ppmsvsr",
            "tensor_backend": "paddle",
            "num_frames": 5,
            "engine": "cuda",
        },
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan(
        StageProjection((step,)),
        make_video_metadata(12, duration=1.0, width=64, height=64),
        output_fps=None,
    )
    worker_config = build_stage_worker_plans(
        stage_plan=stage_plan,
        source_frame_count=12,
    )[0]

    config_path = tmp_path / "stage-worker.json"
    config_path.write_text(worker_config.model_dump_json(by_alias=True), encoding="utf-8")
    parsed = load_stage_worker_config(config_path)

    assert parsed.stage.algorithm_kwargs.num_frames == 5
