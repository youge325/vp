"""Planning-layer workflow-to-stage helpers."""

from app.planning import (
    PROCESS_ORDER_MAP,
    resolve_expected_output_frames,
    resolve_primary_algorithm,
    resolve_processing_steps,
    resolve_workflow_and_output_fps,
)


class _FakeFFmpeg:
    def __init__(self, *, fps: float = 24.0, frame_count: int = 24, duration: float = 1.0):
        self._fps = fps
        self._frame_count = frame_count
        self._duration = duration

    def get_fps(self, _input_path: str) -> float:
        return self._fps

    def get_frame_count(self, _input_path: str) -> int:
        return self._frame_count

    def get_duration(self, _input_path: str) -> float:
        return self._duration


def _workflow(**overrides):
    workflow = {
        "fpsMode": "target",
        "processOrder": "super_resolution_then_interpolation",
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
            "enabled": False,
            "scaleFactor": 2.0,
            "algorithm": "placeholder",
            "tensorBackend": "onnx",
        },
        "anime": {
            "enabled": False,
            "profile": "clean-lines",
            "denoise": 10,
            "edgeBoost": 15,
        },
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }
    workflow.update(overrides)
    return workflow


def test_workflow_step_planning_is_exported_from_planning_layer():
    assert PROCESS_ORDER_MAP["super_resolution_then_interpolation"] == [
        "super_resolution",
        "frame_interpolation",
    ]
    assert resolve_primary_algorithm(_workflow()) == "frame_interpolation"


def test_resolve_processing_steps_builds_ordered_stage_names_and_kwargs():
    steps = resolve_processing_steps(
        _workflow(
            superResolution={
                "enabled": True,
                "scaleFactor": 4.0,
                "algorithm": "ppmsvsr",
                "tensorBackend": "paddle",
                "engine": "cuda",
                "numFrames": 8,
            },
            preprocess={"enabled": True, "filters": [{"kind": "scale"}]},
            postprocess={"enabled": True, "filters": [{"kind": "sharpen"}]},
        )
    )

    assert [step.stage_name for step in steps] == [
        "01_preprocess",
        "02_super_resolution",
        "03_frame_interpolation",
        "04_postprocess",
    ]
    assert steps[1].algorithm_kwargs["tensor_backend"] == "paddle"
    assert steps[1].algorithm_kwargs["num_frames"] == 8
    assert steps[2].algorithm_kwargs["model_version"] == "4.25"


def test_resolve_workflow_and_output_fps_returns_new_workflow_without_mutating_input():
    workflow = _workflow()

    resolved, final_output_fps = resolve_workflow_and_output_fps(
        workflow,
        _FakeFFmpeg(fps=24.0),
        "demo.mp4",
    )

    assert workflow["interpolation"]["multi"] == 2
    assert resolved["interpolation"]["multi"] == 3
    assert final_output_fps == 60.0


def test_resolve_expected_output_frames_uses_interpolation_or_target_timeline():
    workflow = _workflow(fpsMode="multi")
    steps = resolve_processing_steps(workflow)

    assert (
        resolve_expected_output_frames(
            ffmpeg=_FakeFFmpeg(frame_count=12, duration=1.0),
            input_path="demo.mp4",
            workflow_config=workflow,
            processing_steps=steps,
            final_output_fps=None,
        )
        == 23
    )
    assert (
        resolve_expected_output_frames(
            ffmpeg=_FakeFFmpeg(frame_count=12, duration=1.0),
            input_path="demo.mp4",
            workflow_config=workflow,
            processing_steps=steps,
            final_output_fps=60.0,
        )
        == 60
    )
