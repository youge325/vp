"""Streaming pipeline tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from app.planning import SegmentManifest, build_signature
from app.processing.streaming.queues import EncodedFrame, StreamEnd
from app.processing.streaming import process_video_streaming
from app.processing.streaming.worker_plans import (
    boundary_schedule_for_stage_plan,
    build_stage_worker_plans,
)


class _IdentityBackend:
    def numpy_to_tensor(self, frame):
        return frame

    def tensor_to_numpy(self, tensor):
        return tensor

    def get_name(self) -> str:
        return "identity"

    def is_available(self) -> bool:
        return True


class _IdentityAlgorithm:
    def process_frame(self, frame, **kwargs):
        return frame


class _MidpointInterpolationAlgorithm:
    def process_frame_pair(self, frame0, frame1, timestep=0.5, **kwargs):
        del timestep, kwargs
        return ((frame0.astype(np.float32) + frame1.astype(np.float32)) / 2).astype(np.uint8)


class _FakeReader:
    def __init__(self, frames: list[np.ndarray], start_frame: int):
        self._frames = [frame.copy() for frame in frames[start_frame:]]
        self._index = 0

    def read_frame(self) -> np.ndarray | None:
        if self._index >= len(self._frames):
            return None
        frame = self._frames[self._index]
        self._index += 1
        return frame.copy()

    def close(self) -> None:
        return None


class _FakeWriter:
    def __init__(
        self,
        wrapper: "_FakeFFmpegWrapper",
        output_path: str,
        *,
        fps: float,
        output_fps: float | None,
        progress_callback=None,
    ):
        self._wrapper = wrapper
        self._output_path = output_path
        self._fps = fps
        self._output_fps = output_fps or fps
        self._progress_callback = progress_callback
        self._frames: list[np.ndarray] = []
        self.output_frame_count = 0

    def write_frame(self, frame: np.ndarray) -> None:
        self._frames.append(frame.copy())

    def close(self) -> None:
        output_path = Path(self._output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"segment")
        self.output_frame_count = self._resolve_output_frame_count()
        self._wrapper.video_frames[str(output_path)] = self._build_output_frames()
        if self._progress_callback is not None:
            self._progress_callback(
                {
                    "frame": self.output_frame_count,
                    "fps": 48.0,
                    "speed": 1.0,
                    "out_time_seconds": None,
                    "progress": "end",
                }
            )

    def _resolve_output_frame_count(self) -> int:
        if not self._frames:
            return 0
        if abs(self._output_fps - self._fps) <= 0.01:
            return len(self._frames)
        return max(1, int(round(len(self._frames) * self._output_fps / self._fps)))

    def _build_output_frames(self) -> list[np.ndarray]:
        if not self._frames:
            return []
        if self.output_frame_count <= len(self._frames):
            return [frame.copy() for frame in self._frames[: self.output_frame_count]]

        padded_frames = [frame.copy() for frame in self._frames]
        padded_frames.extend(self._frames[-1].copy() for _ in range(self.output_frame_count - len(self._frames)))
        return padded_frames


class _FakeFFmpegWrapper:
    def __init__(self, source_frames: list[np.ndarray], *, source_fps: float = 24.0):
        self._source_frames = [frame.copy() for frame in source_frames]
        self._source_fps = source_fps
        self.video_frames: dict[str, list[np.ndarray]] = {}
        self.encoder_dimensions: list[tuple[int, int]] = []

    def get_video_info(self, _input_path: str):
        height, width, _channels = self._source_frames[0].shape
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "width": width,
                    "height": height,
                }
            ]
        }

    def get_fps(self, _input_path: str) -> float:
        return self._source_fps

    def get_frame_count(self, input_path: str) -> int:
        if input_path in self.video_frames:
            return len(self.video_frames[input_path])
        return len(self._source_frames)

    def get_duration(self, _input_path: str) -> float:
        return len(self._source_frames) / self._source_fps

    def has_audio(self, _input_path: str) -> bool:
        return True

    def open_rawvideo_decoder(self, *, start_frame: int = 0, **kwargs):
        del kwargs
        return _FakeReader(self._source_frames, start_frame)

    def open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        progress_callback=None,
        **kwargs,
    ):
        del kwargs
        self.encoder_dimensions.append((width, height))
        return _FakeWriter(
            self,
            output_path,
            fps=fps,
            output_fps=output_fps,
            progress_callback=progress_callback,
        )

    def concat_videos(self, segment_paths: list[str], output_path: str) -> str:
        frames: list[np.ndarray] = []
        for path in segment_paths:
            frames.extend(self.video_frames[path])
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"concat")
        self.video_frames[str(output)] = [frame.copy() for frame in frames]
        return str(output)

    def extract_audio(self, _input_path: str, output_path: str) -> str:
        audio_path = Path(output_path)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"audio")
        return str(audio_path)

    def merge_audio(self, video_path: str, _audio_path: str, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"final")
        self.video_frames[str(output)] = [frame.copy() for frame in self.video_frames[video_path]]
        return str(output)


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _install_video_frames_rename_hook(monkeypatch: pytest.MonkeyPatch, wrapper: "_FakeFFmpegWrapper") -> None:
    """Patch os.replace inside the encoder so renames propagate to the wrapper."""
    import app.processing.streaming.encoder_finalization as finalization_module

    original_replace = finalization_module.os.replace

    def tracking_replace(src, dst):
        result = original_replace(src, dst)
        src_str = str(src)
        dst_str = str(dst)
        if src_str in wrapper.video_frames:
            wrapper.video_frames[dst_str] = wrapper.video_frames.pop(src_str)
        return result

    monkeypatch.setattr(finalization_module.os, "replace", tracking_replace)


def _install_fake_stage_worker_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_worker_pipeline(**kwargs):
        ffmpeg = kwargs["ffmpeg"]
        stage_plan = kwargs["stage_plan"]
        video_info = kwargs["video_info"]
        resume_state = kwargs["resume_state"]
        encode_queue = kwargs["encode_queue"]
        start = resume_state.start_source_frame
        frames = [frame.copy() for frame in ffmpeg._source_frames[start:]]

        plans = build_stage_worker_plans(
            stage_plan=stage_plan,
            tensor_backend_name=kwargs["tensor_backend_name"],
            source_width=video_info["width"],
            source_height=video_info["height"],
            source_frame_count=len(frames),
        )
        for plan in plans:
            frames = _apply_fake_stage(plan.config.stage, frames, plan.config.output_width, plan.config.output_height)

        schedule = boundary_schedule_for_stage_plan(
            stage_plan=stage_plan,
            start_source_frame=start,
            source_frames=video_info["source_frames"],
        )
        for emitted_count, frame in enumerate(frames, start=1):
            encode_queue.put(EncodedFrame(frame=frame))
            next_source_frame = schedule.get(emitted_count)
            if next_source_frame is not None:
                from app.processing.streaming.queues import SegmentBoundary

                encode_queue.put(SegmentBoundary(next_source_frame=next_source_frame))
        encode_queue.put(StreamEnd(next_source_frame=video_info["source_frames"]))

    monkeypatch.setattr("app.processing.streaming.pipeline_raw.run_stage_worker_pipeline", fake_worker_pipeline)
    monkeypatch.setattr(
        "app.processing.streaming.pipeline_preflight.should_use_stage_file_pipeline",
        lambda _stage_plan: False,
    )


def _apply_fake_stage(step, frames: list[np.ndarray], output_width: int, output_height: int) -> list[np.ndarray]:
    if step.algorithm_type == "frame_interpolation":
        if len(frames) < 2:
            return [frame.copy() for frame in frames]
        multi = int(step.algorithm_kwargs.get("multi") or 2)
        output: list[np.ndarray] = []
        for index in range(len(frames) - 1):
            prev = frames[index]
            cur = frames[index + 1]
            output.append(prev.copy())
            for mid_index in range(1, multi):
                timestep = mid_index / multi
                output.append(
                    np.rint(prev.astype(np.float32) + (cur.astype(np.float32) - prev) * timestep).astype(np.uint8)
                )
        output.append(frames[-1].copy())
        return output
    if step.algorithm_type == "super_resolution" and frames and frames[0].shape[:2] != (output_height, output_width):
        return [_resize_nearest(frame, output_width=output_width, output_height=output_height) for frame in frames]
    return [frame.copy() for frame in frames]


def _resize_nearest(frame: np.ndarray, *, output_width: int, output_height: int) -> np.ndarray:
    height, width, _channels = frame.shape
    y_indexes = np.minimum((np.arange(output_height) * height / output_height).astype(int), height - 1)
    x_indexes = np.minimum((np.arange(output_width) * width / output_width).astype(int), width - 1)
    return frame[y_indexes][:, x_indexes].copy()


def _workspace(name: str) -> Path:
    root = Path("D:/Lenovo/vp/.tmp/test_streaming") / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _workflow_config(segment_frames: int = 2) -> tuple[dict, dict, list[dict], dict]:
    workflow_config = {
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
            "scaleFactor": 2.0,
            "algorithm": "placeholder",
        },
    }
    encode_config = {
        "codec": "libx264",
        "family": "cpu",
        "container": "mp4",
        "keepAudio": True,
        "rateControl": {"mode": "crf", "value": 18},
        "options": {},
    }
    processing_steps = [
        {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {"multi": 2, "model_version": "4.25", "scale": 1.0, "fp16": False},
            "stage_name": "01_frame_interpolation",
        },
        {
            "algorithm_type": "super_resolution",
            "algorithm_kwargs": {"scale_factor": 2.0, "sr_algorithm": "placeholder"},
            "stage_name": "02_super_resolution",
        },
    ]
    output_config = {"outputDir": "", "openOnComplete": False, "segmentFrames": segment_frames}
    return workflow_config, encode_config, processing_steps, output_config


def test_streaming_pipeline_resumes_without_duplicate_frames(monkeypatch):
    source_frames = [_frame(0), _frame(100), _frame(200)]
    wrapper = _FakeFFmpegWrapper(source_frames)
    workspace = _workspace("resume")
    input_path = workspace / "input.mp4"
    output_path = workspace / "output" / "demo_processed.mp4"
    input_path.write_bytes(b"input")

    workflow_config, encode_config, processing_steps, output_config = _workflow_config(segment_frames=2)
    decode_config = {"mode": "software", "decoder": "software", "options": {}}
    video_info = {
        "width": 1,
        "height": 1,
        "source_fps": 24.0,
        "source_frames": len(source_frames),
        "duration": len(source_frames) / 24.0,
        "has_audio": True,
    }
    signature = build_signature(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        video_info=video_info,
    )
    manifest = SegmentManifest(str(output_path))
    decision = manifest.prepare(signature, {}, mode="auto")
    assert decision.kind == "fresh"
    first_segment_tmp = manifest.chunk_tmp_path(".mp4", index=1)
    Path(first_segment_tmp).write_bytes(b"segment-1")
    first_segment = manifest.finalize_chunk(
        first_segment_tmp,
        index=1,
        start_output_frame=0,
        end_output_frame=1,
        next_source_frame=1,
    )
    wrapper.video_frames[str(Path(first_segment))] = [_frame(0), _frame(50)]

    _install_video_frames_rename_hook(monkeypatch, wrapper)
    _install_fake_stage_worker_pipeline(monkeypatch)

    result = process_video_streaming(
        ffmpeg=wrapper,
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args: None, lambda *_args: None],
    )

    assert result["output_path"] == str(output_path)
    assert result["processed_frames"] == 5
    assert [int(frame[0, 0, 0]) for frame in wrapper.video_frames[str(output_path)]] == [0, 50, 100, 150, 200]
    assert not manifest.sidecar_dir.exists()
    assert not any(path.is_dir() and path.name == "frames" for path in workspace.rglob("*"))
    assert not any(path.is_dir() and path.name.startswith("processed_") for path in workspace.rglob("*"))


def test_streaming_pipeline_keeps_sidecar_when_finalization_fails(monkeypatch):
    source_frames = [_frame(0), _frame(100)]
    wrapper = _FakeFFmpegWrapper(source_frames)
    workspace = _workspace("finalize_failure")
    input_path = workspace / "input.mp4"
    output_path = workspace / "output" / "demo_processed.mp4"
    input_path.write_bytes(b"input")

    workflow_config, encode_config, processing_steps, output_config = _workflow_config(segment_frames=2)
    decode_config = {"mode": "software", "decoder": "software", "options": {}}

    _install_video_frames_rename_hook(monkeypatch, wrapper)
    _install_fake_stage_worker_pipeline(monkeypatch)

    def fail_finalize(**kwargs):
        del kwargs
        raise RuntimeError("concat failed")

    monkeypatch.setattr("app.processing.streaming.pipeline_lifecycle.finalize_segmented_output", fail_finalize)

    with pytest.raises(RuntimeError, match="concat failed"):
        process_video_streaming(
            ffmpeg=wrapper,
            input_path=str(input_path),
            output_path=str(output_path),
            decode_config=decode_config,
            encode_config=encode_config,
            workflow_config=workflow_config,
            output_config=output_config,
            processing_steps=processing_steps,
            tensor_backend_name="pytorch",
            progress_callbacks=[lambda *_args: None, lambda *_args: None],
        )

    manifest = SegmentManifest(str(output_path))
    assert manifest.sidecar_dir.exists()
    assert manifest.manifest_path.is_file()
    assert any(path.suffix == ".mp4" for path in manifest.sidecar_dir.iterdir())


def test_streaming_pipeline_reports_final_encoded_frames_when_resampling(monkeypatch):
    source_frames = [_frame(0), _frame(100), _frame(200)]
    wrapper = _FakeFFmpegWrapper(source_frames, source_fps=2.0)
    workspace = _workspace("target_fps")
    input_path = workspace / "input.mp4"
    output_path = workspace / "output" / "demo_processed.mp4"
    input_path.write_bytes(b"input")

    workflow_config, encode_config, processing_steps, output_config = _workflow_config(segment_frames=2)
    decode_config = {"mode": "software", "decoder": "software", "options": {}}

    _install_video_frames_rename_hook(monkeypatch, wrapper)
    _install_fake_stage_worker_pipeline(monkeypatch)

    result = process_video_streaming(
        ffmpeg=wrapper,
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args: None, lambda *_args: None],
        output_fps=3.0,
    )

    assert result["processed_frames"] == len(wrapper.video_frames[str(output_path)])
    assert result["processed_frames"] == 5


def test_streaming_pipeline_uses_scaled_encoder_dimensions_for_onnx_super_resolution(monkeypatch):
    source_frames = [_frame(0), _frame(100)]
    wrapper = _FakeFFmpegWrapper(source_frames)
    workspace = _workspace("onnx_sr_dimensions")
    input_path = workspace / "input.mp4"
    output_path = workspace / "output" / "demo_processed.mp4"
    input_path.write_bytes(b"input")

    workflow_config = {
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
            "onnxModel": "",
        },
        "superResolution": {
            "enabled": True,
            "scaleFactor": 2.0,
            "algorithm": "onnx",
            "onnxModel": "sr.onnx",
        },
    }
    encode_config = {
        "codec": "libx264",
        "family": "cpu",
        "container": "mp4",
        "keepAudio": True,
        "rateControl": {"mode": "crf", "value": 18},
        "options": {},
    }
    processing_steps = [
        {
            "algorithm_type": "super_resolution",
            "algorithm_kwargs": {"scale_factor": 2.0, "sr_algorithm": "onnx", "onnx_model": "sr.onnx"},
            "stage_name": "01_super_resolution",
        }
    ]
    output_config = {"outputDir": "", "openOnComplete": False, "segmentFrames": 2}

    _install_video_frames_rename_hook(monkeypatch, wrapper)
    _install_fake_stage_worker_pipeline(monkeypatch)

    process_video_streaming(
        ffmpeg=wrapper,
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config={"mode": "software", "decoder": "software", "options": {}},
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        tensor_backend_name="onnx",
        progress_callbacks=[lambda *_args: None],
    )

    assert wrapper.encoder_dimensions[0] == (2, 2)


def test_streaming_pipeline_uses_stage_worker_pipeline_for_processing_steps(monkeypatch):
    source_frames = [_frame(7)]
    wrapper = _FakeFFmpegWrapper(source_frames)
    workspace = _workspace("stage_worker_dispatch")
    input_path = workspace / "input.mp4"
    output_path = workspace / "output" / "demo_processed.mp4"
    input_path.write_bytes(b"input")

    workflow_config, encode_config, _processing_steps, output_config = _workflow_config(segment_frames=2)
    processing_steps = [
        {
            "algorithm_type": "super_resolution",
            "algorithm_kwargs": {"scale_factor": 1.0, "sr_algorithm": "placeholder"},
            "stage_name": "01_super_resolution",
        }
    ]
    calls = []

    def fake_worker_pipeline(**kwargs):
        calls.append(kwargs["stage_plan"])
        kwargs["encode_queue"].put(EncodedFrame(frame=_frame(9)))
        kwargs["encode_queue"].put(StreamEnd(next_source_frame=1))

    _install_video_frames_rename_hook(monkeypatch, wrapper)
    monkeypatch.setattr("app.processing.streaming.pipeline_raw.run_stage_worker_pipeline", fake_worker_pipeline)

    process_video_streaming(
        ffmpeg=wrapper,
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config={"mode": "software", "decoder": "software", "options": {}},
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        tensor_backend_name="onnx",
        progress_callbacks=[lambda *_args: None],
    )

    assert len(calls) == 1
    assert [int(frame[0, 0, 0]) for frame in wrapper.video_frames[str(output_path)]] == [9]


def test_legacy_processing_modules_are_removed():
    processing_dir = Path(__file__).resolve().parents[2] / "app" / "processing"

    assert not (processing_dir / "pipeline.py").exists()
    assert not (processing_dir / "decoder.py").exists()
    assert not (processing_dir / "encoder.py").exists()
    assert not (processing_dir / "frame_processor.py").exists()
