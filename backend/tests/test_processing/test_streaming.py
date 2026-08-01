"""Streaming pipeline tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import numpy as np
import pytest

from app.planning.processing_steps import ProcessingStep
from app.planning.run_identity import build_run_identity
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.metrics import PipelineMetrics
from tests.support.streaming_runtime import create_test_manifest, ignore_resume_status, ignore_worker_log
from app.processing.streaming.queues import EncodedFrame, StreamEnd
from app.processing.streaming.pipeline import process_video_streaming
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight
from app.processing.streaming.worker_plans import (
    boundary_schedule_for_stage_plan,
    build_stage_worker_plans,
)


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
        wrapper: "_FakeMediaRuntime",
        output_path: str,
        *,
        fps: float,
        output_fps: float | None,
        progress_callback=None,
        progress_frame_offset: int = 0,
    ):
        self._wrapper = wrapper
        self._output_path = output_path
        self._fps = fps
        self._output_fps = output_fps or fps
        self._progress_callback = progress_callback
        self._progress_frame_offset = progress_frame_offset
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
                self._progress_frame_offset + self.output_frame_count,
                48.0,
                1.0,
                None,
                "end",
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


class _FakeMediaRuntime:
    def __init__(self, source_frames: list[np.ndarray], *, source_fps: float = 24.0):
        self._source_frames = [frame.copy() for frame in source_frames]
        self._source_fps = source_fps
        self.video_frames: dict[str, list[np.ndarray]] = {}
        self.encoder_dimensions: list[tuple[int, int]] = []

    def probe_video(self, _input_path: str) -> VideoMetadata:
        height, width, _channels = self._source_frames[0].shape
        return VideoMetadata(
            width=width,
            height=height,
            source_fps=self._source_fps,
            source_frames=len(self._source_frames),
            duration=len(self._source_frames) / self._source_fps,
            has_audio=True,
        )

    def get_frame_count(self, input_path: str) -> int:
        if input_path in self.video_frames:
            return len(self.video_frames[input_path])
        return len(self._source_frames)

    def open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config=None,
        start_frame: int = 0,
        frame_count: int | None = None,
    ):
        del input_path, width, height, decode_config, frame_count
        return _FakeReader(self._source_frames, start_frame)

    def open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config=None,
        progress_callback=None,
        progress_frame_offset: int = 0,
    ):
        del encode_config
        self.encoder_dimensions.append((width, height))
        return _FakeWriter(
            self,
            output_path,
            fps=fps,
            output_fps=output_fps,
            progress_callback=progress_callback,
            progress_frame_offset=progress_frame_offset,
        )

    def concat_videos(self, segment_paths: list[str], output_path: str) -> None:
        frames: list[np.ndarray] = []
        for path in segment_paths:
            frames.extend(self.video_frames[path])
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"concat")
        self.video_frames[str(output)] = [frame.copy() for frame in frames]

    def extract_audio(self, _input_path: str, output_path: str) -> bool:
        audio_path = Path(output_path)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"audio")
        return True

    def merge_audio(self, video_path: str, _audio_path: str, output_path: str) -> None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"final")
        self.video_frames[str(output)] = [frame.copy() for frame in self.video_frames[video_path]]


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _install_video_frames_rename_hook(monkeypatch: pytest.MonkeyPatch, wrapper: "_FakeMediaRuntime") -> None:
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
        config = kwargs["config"]
        ffmpeg = config.ffmpeg
        stage_plan = config.stage_plan
        resume_state = config.resume_state
        encode_queue = kwargs["encode_queue"]
        start = resume_state.start_source_frame
        frames = [frame.copy() for frame in ffmpeg._source_frames[start:]]

        plans = build_stage_worker_plans(
            stage_plan=stage_plan,
            source_width=config.source_width,
            source_height=config.source_height,
            source_frame_count=len(frames),
        )
        for worker_config in plans:
            frames = _apply_fake_stage(
                worker_config.stage,
                frames,
                worker_config.output_width,
                worker_config.output_height,
            )

        schedule = boundary_schedule_for_stage_plan(
            stage_plan=stage_plan,
            start_source_frame=start,
            source_frames=config.source_frames,
        )
        for emitted_count, frame in enumerate(frames, start=1):
            encode_queue.put(EncodedFrame(frame=frame))
            next_source_frame = schedule.get(emitted_count)
            if next_source_frame is not None:
                from app.processing.streaming.queues import SegmentBoundary

                encode_queue.put(SegmentBoundary(next_source_frame=next_source_frame))
        encode_queue.put(StreamEnd(next_source_frame=config.source_frames))

    monkeypatch.setattr("app.processing.streaming.pipeline_raw.run_stage_worker_pipeline", fake_worker_pipeline)


def _apply_fake_stage(step, frames: list[np.ndarray], output_width: int, output_height: int) -> list[np.ndarray]:
    if step.algorithm_type == "frame_interpolation":
        if len(frames) < 2:
            return [frame.copy() for frame in frames]
        multi = int(step.algorithm_kwargs.multi)
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


def _workflow_config(segment_frames: int = 2) -> tuple[dict, dict, list[ProcessingStep], dict]:
    workflow_config = {
        "fpsMode": "multi",
        "processOrder": "frame_interpolation_then_super_resolution",
        "interpolation": {
            "enabled": False,
            "targetFps": 60,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "pytorch",
            "engine": "cuda",
        },
        "superResolution": {
            "enabled": True,
            "scaleFactor": 2.0,
            "algorithm": "placeholder",
            "onnxModel": "sr.onnx",
            "tensorBackend": "onnx",
            "engine": "cuda",
            "numFrames": 10,
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
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 2.0,
                "sr_algorithm": "placeholder",
                "onnx_model": "sr.onnx",
                "engine": "cuda",
                "tensor_backend": "onnx",
            },
            stage_name="01_super_resolution",
        ),
    ]
    output_config = {"outputDir": "", "openOnComplete": False, "segmentFrames": segment_frames}
    return workflow_config, encode_config, processing_steps, output_config


def _preflight(
    *,
    ffmpeg,
    input_path: Path,
    output_path: Path,
    decode_config: dict,
    encode_config: dict,
    workflow_config: dict,
    output_config: dict,
    processing_steps: list[ProcessingStep],
    output_fps: float | None = None,
):
    return build_streaming_pipeline_preflight(
        video_info=ffmpeg.probe_video(str(input_path)),
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        projection=StageProjection(tuple(processing_steps)),
        output_fps=output_fps,
    )


@dataclass(frozen=True)
class _StreamingCase:
    wrapper: _FakeMediaRuntime
    workspace: Path
    input_path: Path
    output_path: Path
    workflow_config: dict
    encode_config: dict
    processing_steps: list[ProcessingStep]
    output_config: dict
    decode_config: dict


def _streaming_case(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    source_frames: list[np.ndarray],
    *,
    source_fps: float = 24.0,
    install_worker: bool = True,
) -> _StreamingCase:
    wrapper = _FakeMediaRuntime(source_frames, source_fps=source_fps)
    workspace = _workspace(name)
    input_path = workspace / "input.mp4"
    input_path.write_bytes(b"input")
    workflow_config, encode_config, processing_steps, output_config = _workflow_config(segment_frames=2)
    case = _StreamingCase(
        wrapper=wrapper,
        workspace=workspace,
        input_path=input_path,
        output_path=workspace / "output" / "demo_processed.mp4",
        workflow_config=workflow_config,
        encode_config=encode_config,
        processing_steps=processing_steps,
        output_config=output_config,
        decode_config={"mode": "software", "decoder": "software", "options": {}},
    )
    _install_video_frames_rename_hook(monkeypatch, wrapper)
    if install_worker:
        _install_fake_stage_worker_pipeline(monkeypatch)
    return case


def _run_streaming_case(
    case: _StreamingCase,
    *,
    workflow_config: dict | None = None,
    encode_config: dict | None = None,
    processing_steps: list[ProcessingStep] | None = None,
    output_fps: float | None = None,
):
    resolved_workflow = workflow_config or case.workflow_config
    resolved_encode = encode_config or case.encode_config
    resolved_steps = processing_steps or case.processing_steps
    return process_video_streaming(
        ffmpeg=case.wrapper,
        input_path=str(case.input_path),
        output_path=str(case.output_path),
        decode_config=case.decode_config,
        encode_config=resolved_encode,
        preflight=_preflight(
            ffmpeg=case.wrapper,
            input_path=case.input_path,
            output_path=case.output_path,
            decode_config=case.decode_config,
            encode_config=resolved_encode,
            workflow_config=resolved_workflow,
            output_config=case.output_config,
            processing_steps=resolved_steps,
            output_fps=output_fps,
        ),
        progress_callbacks=[lambda *_args: None for _step in resolved_steps],
        metrics=PipelineMetrics(),
        output_fps=output_fps,
        manifest_factory=create_test_manifest,
        resume_status_sink=ignore_resume_status,
        worker_log_sink=ignore_worker_log,
    )


def test_streaming_pipeline_resumes_without_duplicate_frames(monkeypatch):
    source_frames = [_frame(0), _frame(100), _frame(200)]
    case = _streaming_case(monkeypatch, "resume", source_frames)
    video_info = VideoMetadata(
        width=1,
        height=1,
        source_fps=24.0,
        source_frames=len(source_frames),
        duration=len(source_frames) / 24.0,
        has_audio=True,
    )
    identity = build_run_identity(
        input_path=str(case.input_path),
        output_path=str(case.output_path),
        decode_config=case.decode_config,
        encode_config=case.encode_config,
        workflow_config=case.workflow_config,
        output_config=case.output_config,
        processing_steps=case.processing_steps,
        video_info=video_info,
    )
    manifest = create_test_manifest(str(case.output_path))
    decision = manifest.prepare(identity.signature, identity.config_snapshot, mode="auto")
    assert decision.kind == "fresh"
    first_segment_tmp = manifest.workspace.chunk_tmp_path(".mp4", index=1)
    Path(first_segment_tmp).write_bytes(b"segment-1")
    manifest.workspace.finalize_chunk(
        first_segment_tmp,
        index=1,
        start_output_frame=0,
        end_output_frame=0,
        next_source_frame=1,
    )
    first_segment = manifest.workspace.sidecar_dir / manifest.scan_completed_chunks()[0].path
    case.wrapper.video_frames[str(first_segment)] = [_frame(0)]

    result = _run_streaming_case(case)

    assert result.output_path == str(case.output_path)
    assert result.processed_frames == 3
    assert [int(frame[0, 0, 0]) for frame in case.wrapper.video_frames[str(case.output_path)]] == [0, 100, 200]
    assert not manifest.workspace.sidecar_dir.exists()
    assert not any(path.is_dir() and path.name == "frames" for path in case.workspace.rglob("*"))
    assert not any(path.is_dir() and path.name.startswith("processed_") for path in case.workspace.rglob("*"))


def test_streaming_pipeline_keeps_sidecar_when_finalization_fails(monkeypatch):
    case = _streaming_case(monkeypatch, "finalize_failure", [_frame(0), _frame(100)])

    def fail_finalize(**kwargs):
        del kwargs
        raise RuntimeError("concat failed")

    monkeypatch.setattr("app.processing.streaming.pipeline_lifecycle.finalize_segmented_output", fail_finalize)

    with pytest.raises(RuntimeError, match="concat failed"):
        _run_streaming_case(case)

    manifest = create_test_manifest(str(case.output_path))
    assert manifest.workspace.sidecar_dir.exists()
    assert manifest.workspace.manifest_path.is_file()
    assert any(path.suffix == ".mp4" for path in manifest.workspace.sidecar_dir.iterdir())


def test_streaming_pipeline_reports_final_encoded_frames_when_resampling(monkeypatch):
    case = _streaming_case(monkeypatch, "target_fps", [_frame(0), _frame(100), _frame(200)], source_fps=2.0)

    result = _run_streaming_case(case, output_fps=3.0)

    assert result.processed_frames == len(case.wrapper.video_frames[str(case.output_path)])
    assert result.processed_frames == 5


def test_streaming_pipeline_uses_scaled_encoder_dimensions_for_onnx_super_resolution(monkeypatch):
    case = _streaming_case(monkeypatch, "onnx_sr_dimensions", [_frame(0), _frame(100)])
    workflow_config, encode_config, _default_steps, _output_config = _workflow_config()
    workflow_config["processOrder"] = "super_resolution_then_interpolation"
    workflow_config["interpolation"].update(enabled=False, tensorBackend="onnx", onnxModel="")
    processing_steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 2.0,
                "sr_algorithm": "placeholder",
                "onnx_model": "sr.onnx",
                "engine": "cuda",
                "tensor_backend": "onnx",
            },
            stage_name="01_super_resolution",
        )
    ]

    _run_streaming_case(
        case,
        workflow_config=workflow_config,
        encode_config=encode_config,
        processing_steps=processing_steps,
    )

    assert case.wrapper.encoder_dimensions[0] == (2, 2)


def test_streaming_pipeline_uses_stage_worker_pipeline_for_processing_steps(monkeypatch):
    case = _streaming_case(monkeypatch, "stage_worker_dispatch", [_frame(7)], install_worker=False)
    processing_steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 1.0,
                "sr_algorithm": "placeholder",
                "onnx_model": "sr.onnx",
                "engine": "cuda",
                "tensor_backend": "onnx",
            },
            stage_name="01_super_resolution",
        )
    ]
    calls = []

    def fake_worker_pipeline(**kwargs):
        calls.append(kwargs["config"].stage_plan)
        kwargs["encode_queue"].put(EncodedFrame(frame=_frame(9)))
        kwargs["encode_queue"].put(StreamEnd(next_source_frame=1))

    monkeypatch.setattr("app.processing.streaming.pipeline_raw.run_stage_worker_pipeline", fake_worker_pipeline)

    _run_streaming_case(case, processing_steps=processing_steps)

    assert len(calls) == 1
    assert [int(frame[0, 0, 0]) for frame in case.wrapper.video_frames[str(case.output_path)]] == [9]
