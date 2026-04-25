"""Streaming video processing with bounded queues and segmented output."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.config import settings
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DECODE_END = object()
_ENCODE_END = object()


@dataclass(slots=True)
class DecodedFrame:
    """Decoded source frame packet."""

    source_index: int
    frame: np.ndarray


@dataclass(slots=True)
class EncodedFrame:
    """Processed frame ready to feed the encoder."""

    output_index: int
    frame: np.ndarray


@dataclass(slots=True)
class SegmentBoundary:
    """Natural split point after a full source-frame group."""

    next_source_frame: int


@dataclass(slots=True)
class StreamEnd:
    """Signal end-of-stream to the encoder stage."""

    next_source_frame: int


@dataclass(slots=True)
class SegmentRecord:
    """One completed temporary segment."""

    index: int
    path: str
    start_output_frame: int
    end_output_frame: int
    frame_count: int
    next_source_frame: int


@dataclass(slots=True)
class ResumeState:
    """Resume information loaded from the segment manifest."""

    start_source_frame: int
    completed_output_frames: int
    completed_segments: list[SegmentRecord]


@dataclass(slots=True)
class StagePlan:
    """Resolved processing layout for the streaming executor."""

    pre_steps: list[dict[str, Any]]
    interpolation_step: dict[str, Any] | None
    post_steps: list[dict[str, Any]]
    total_output_frames: int
    total_encoded_frames: int
    total_pairs: int


class SegmentManifest:
    """Internal manifest that tracks completed temporary segments."""

    MANIFEST_VERSION = 1

    def __init__(self, output_path: str):
        output = Path(output_path)
        self.output_path = output.resolve()
        self.sidecar_dir = self.output_path.with_name(f"{self.output_path.name}.vp_segments")
        self.manifest_path = self.sidecar_dir / "manifest.json"

    def prepare(self, signature: str) -> ResumeState:
        """Prepare sidecar state for a new run or a resume."""
        if self.output_path.exists():
            self._reset_sidecar()
            self._write_manifest(signature, [])
            return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])

        if not self.manifest_path.is_file():
            self.sidecar_dir.mkdir(parents=True, exist_ok=True)
            self._write_manifest(signature, [])
            return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])

        manifest = self._load_manifest()
        if manifest.get("signature") != signature:
            self._reset_sidecar()
            self.sidecar_dir.mkdir(parents=True, exist_ok=True)
            self._write_manifest(signature, [])
            return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])

        cleaned_records = self._collect_contiguous_completed_segments(manifest.get("segments", []))
        self._remove_unknown_files(cleaned_records)
        self._write_manifest(signature, cleaned_records)

        completed_output_frames = sum(record["frame_count"] for record in cleaned_records)
        start_source_frame = cleaned_records[-1]["next_source_frame"] if cleaned_records else 0
        return ResumeState(
            start_source_frame=start_source_frame,
            completed_output_frames=completed_output_frames,
            completed_segments=[self._dict_to_record(record) for record in cleaned_records],
        )

    def record_segment(
        self,
        signature: str,
        *,
        index: int,
        path: str,
        start_output_frame: int,
        end_output_frame: int,
        frame_count: int,
        next_source_frame: int,
    ) -> None:
        """Persist one completed segment."""
        manifest = self._load_manifest(default_signature=signature)
        records = manifest.get("segments", [])
        record = {
            "index": index,
            "path": os.path.basename(path),
            "start_output_frame": start_output_frame,
            "end_output_frame": end_output_frame,
            "frame_count": frame_count,
            "next_source_frame": next_source_frame,
        }

        replaced = False
        for idx, existing in enumerate(records):
            if existing.get("index") == index:
                records[idx] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
            records.sort(key=lambda item: item["index"])

        self._write_manifest(signature, records)

    def segment_path(self, index: int, extension: str) -> str:
        """Return the temporary segment path for the given index."""
        resolved_extension = extension if extension.startswith(".") else f".{extension}"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        return str(self.sidecar_dir / f"segment_{index:04d}{resolved_extension}")

    def concat_temp_path(self, extension: str) -> str:
        """Return the temporary concat output path inside the sidecar directory."""
        resolved_extension = extension if extension.startswith(".") else f".{extension}"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        return str(self.sidecar_dir / f"concat_noaudio{resolved_extension}")

    def cleanup(self) -> None:
        """Delete the sidecar directory after a successful run."""
        if self.sidecar_dir.is_dir():
            shutil.rmtree(self.sidecar_dir)

    def read_completed_segments(self) -> list[SegmentRecord]:
        """Read the contiguous completed segment list without resetting state."""
        manifest = self._load_manifest()
        records = self._collect_contiguous_completed_segments(manifest.get("segments", []))
        return [self._dict_to_record(record) for record in records]

    def _reset_sidecar(self) -> None:
        if self.sidecar_dir.is_dir():
            shutil.rmtree(self.sidecar_dir)

    def _load_manifest(self, default_signature: str | None = None) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {
                "version": self.MANIFEST_VERSION,
                "signature": default_signature or "",
                "segments": [],
            }
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_manifest(self, signature: str, segments: list[dict[str, Any]]) -> None:
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.MANIFEST_VERSION,
            "signature": signature,
            "segments": segments,
        }
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _collect_contiguous_completed_segments(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        completed: list[dict[str, Any]] = []
        expected_index = 1
        expected_start = 0

        for record in sorted(records, key=lambda item: item.get("index", 0)):
            path = self.sidecar_dir / str(record.get("path", ""))
            if record.get("index") != expected_index:
                break
            if record.get("start_output_frame") != expected_start:
                break
            if not path.is_file():
                break

            completed.append(
                {
                    "index": expected_index,
                    "path": path.name,
                    "start_output_frame": int(record.get("start_output_frame", 0)),
                    "end_output_frame": int(record.get("end_output_frame", -1)),
                    "frame_count": int(record.get("frame_count", 0)),
                    "next_source_frame": int(record.get("next_source_frame", 0)),
                }
            )
            expected_index += 1
            expected_start += int(record.get("frame_count", 0))

        return completed

    def _remove_unknown_files(self, records: list[dict[str, Any]]) -> None:
        keep_names = {self.manifest_path.name, *(record["path"] for record in records)}
        if not self.sidecar_dir.is_dir():
            return

        for item in self.sidecar_dir.iterdir():
            if item.name in keep_names:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)

    @staticmethod
    def _dict_to_record(payload: dict[str, Any]) -> SegmentRecord:
        return SegmentRecord(
            index=int(payload["index"]),
            path=str(payload["path"]),
            start_output_frame=int(payload["start_output_frame"]),
            end_output_frame=int(payload["end_output_frame"]),
            frame_count=int(payload["frame_count"]),
            next_source_frame=int(payload["next_source_frame"]),
        )


def process_video_streaming(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    output_fps: float | None = None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None = None,
) -> dict[str, Any]:
    """Process a video without writing temporary frames to disk."""
    video_info = _resolve_video_info(ffmpeg, input_path)
    stage_plan = _build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=output_fps,
    )
    signature = _build_signature(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        video_info=video_info,
    )

    manifest = SegmentManifest(output_path)
    resume_state = manifest.prepare(signature)

    if resume_state.start_source_frame >= video_info["source_frames"]:
        completed_output_frames = resume_state.completed_output_frames
    else:
        completed_output_frames = _run_streaming_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            manifest=manifest,
            signature=signature,
            stage_plan=stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=video_info,
            resume_state=resume_state,
            segment_frames=max(1, int(output_config.get("segmentFrames") or 1000)),
            output_path=output_path,
            output_fps=output_fps,
            encode_progress_callback=encode_progress_callback,
        )

    final_output = _finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        encode_config=encode_config,
        manifest=manifest,
        signature=signature,
        completed_output_frames=completed_output_frames,
        total_output_frames=stage_plan.total_encoded_frames,
        strict_total_frames=output_fps is None,
    )

    manifest.cleanup()
    processed_frames = ffmpeg.get_frame_count(final_output)
    return {
        "output_path": final_output,
        "processed_frames": processed_frames or completed_output_frames,
        "audio_merged": bool(encode_config.get("keepAudio", True)),
    }


def _resolve_video_info(ffmpeg: FFmpegWrapper, input_path: str) -> dict[str, Any]:
    info = ffmpeg.get_video_info(input_path)
    width = 0
    height = 0
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            break

    if width <= 0 or height <= 0:
        raise RuntimeError(f"Unable to resolve video dimensions for {input_path}")

    source_fps = ffmpeg.get_fps(input_path)
    source_frames = ffmpeg.get_frame_count(input_path)
    if source_frames <= 0:
        raise RuntimeError(f"Unable to resolve source frame count for {input_path}")

    return {
        "width": width,
        "height": height,
        "source_fps": source_fps,
        "source_frames": source_frames,
        "duration": ffmpeg.get_duration(input_path),
        "has_audio": ffmpeg.has_audio(input_path),
    }


def _build_stage_plan(
    processing_steps: list[dict[str, Any]],
    source_frames: int,
    *,
    source_duration: float,
    output_fps: float | None,
) -> StagePlan:
    interpolation_index = None
    for index, step in enumerate(processing_steps):
        if step["algorithm_type"] == "frame_interpolation":
            interpolation_index = index
            break

    if interpolation_index is None:
        total_encoded_frames = _estimate_encoded_output_frames(
            source_frames=source_frames,
            source_duration=source_duration,
            output_fps=output_fps,
        )
        return StagePlan(
            pre_steps=processing_steps,
            interpolation_step=None,
            post_steps=[],
            total_output_frames=source_frames,
            total_encoded_frames=total_encoded_frames,
            total_pairs=max(source_frames - 1, 0),
        )

    interpolation_step = processing_steps[interpolation_index]
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or settings.RIFE_DEFAULT_MULTI)
    if source_frames < 2:
        total_output_frames = source_frames
        total_pairs = 0
    else:
        total_output_frames = source_frames + (source_frames - 1) * (multi - 1)
        total_pairs = source_frames - 1
    total_encoded_frames = _estimate_encoded_output_frames(
        source_frames=total_output_frames,
        source_duration=source_duration,
        output_fps=output_fps,
    )

    return StagePlan(
        pre_steps=processing_steps[:interpolation_index],
        interpolation_step=interpolation_step,
        post_steps=processing_steps[interpolation_index + 1 :],
        total_output_frames=total_output_frames,
        total_encoded_frames=total_encoded_frames,
        total_pairs=total_pairs,
    )


def _estimate_encoded_output_frames(
    *,
    source_frames: int,
    source_duration: float,
    output_fps: float | None,
) -> int:
    if output_fps is None:
        return source_frames
    if source_duration <= 0:
        return source_frames
    return max(1, int(round(source_duration * output_fps)))


def _build_signature(
    *,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    video_info: dict[str, Any],
) -> str:
    stat = os.stat(input_path)
    payload = {
        "input_path": os.path.abspath(input_path),
        "output_path": os.path.abspath(output_path),
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
        "decode_config": decode_config,
        "encode_config": encode_config,
        "workflow_config": workflow_config,
        "output_config": {
            "segmentFrames": max(1, int(output_config.get("segmentFrames") or 1000)),
        },
        "processing_steps": processing_steps,
        "video_info": {
            "width": video_info["width"],
            "height": video_info["height"],
            "source_fps": video_info["source_fps"],
            "source_frames": video_info["source_frames"],
        },
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_streaming_pipeline(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    segment_frames: int,
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> int:
    decode_queue: queue.Queue[DecodedFrame | object] = queue.Queue(maxsize=8)
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    thread_args = {
        "decode_queue": decode_queue,
        "encode_queue": encode_queue,
        "error_queue": error_queue,
        "stop_event": stop_event,
    }

    threads = [
        threading.Thread(
            target=_decoder_worker,
            name="vp-decoder",
            kwargs={
                **thread_args,
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "width": video_info["width"],
                "height": video_info["height"],
                "start_source_frame": resume_state.start_source_frame,
                "source_frames": video_info["source_frames"],
            },
            daemon=True,
        ),
        threading.Thread(
            target=_processor_worker,
            name="vp-processor",
            kwargs={
                **thread_args,
                "stage_plan": stage_plan,
                "tensor_backend_name": tensor_backend_name,
                "progress_callbacks": progress_callbacks,
                "source_frames": video_info["source_frames"],
                "resume_output_frames": resume_state.completed_output_frames,
            },
            daemon=True,
        ),
        threading.Thread(
            target=_encoder_worker,
            name="vp-encoder",
            kwargs={
                **thread_args,
                "ffmpeg": ffmpeg,
                "encode_config": encode_config,
                "manifest": manifest,
                "signature": signature,
                "width": video_info["width"],
                "height": video_info["height"],
                "fps": _resolved_stream_fps(video_info["source_fps"], stage_plan),
                "output_fps": output_fps,
                "segment_frames": segment_frames,
                "resume_state": resume_state,
                "output_path": output_path,
                "encode_progress_callback": encode_progress_callback,
            },
            daemon=True,
        ),
    ]

    if encode_progress_callback is not None and resume_state.completed_output_frames > 0:
        encode_progress_callback(
            resume_state.completed_output_frames,
            None,
            None,
            None,
            "continue",
        )

    for worker in threads:
        worker.start()

    for worker in threads:
        worker.join()

    if not error_queue.empty():
        raise error_queue.get()

    del signature
    completed_segments = manifest.read_completed_segments()
    return sum(segment.frame_count for segment in completed_segments)


def _resolved_stream_fps(source_fps: float, stage_plan: StagePlan) -> float:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        return source_fps
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or settings.RIFE_DEFAULT_MULTI)
    return source_fps * multi


def _decoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    width: int,
    height: int,
    start_source_frame: int,
    source_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    del encode_queue
    try:
        if start_source_frame >= source_frames:
            _queue_put(decode_queue, _DECODE_END, stop_event)
            return

        reader = ffmpeg.open_rawvideo_decoder(
            input_path=input_path,
            width=width,
            height=height,
            decode_config=decode_config,
            start_frame=start_source_frame,
        )
        try:
            source_index = start_source_frame
            while not stop_event.is_set():
                frame = reader.read_frame()
                if frame is None:
                    break
                _queue_put(decode_queue, DecodedFrame(source_index=source_index, frame=frame), stop_event)
                source_index += 1
        finally:
            reader.close()

        _queue_put(decode_queue, _DECODE_END, stop_event)
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(decode_queue, _DECODE_END)


def _processor_worker(
    *,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    try:
        algorithms = _initialize_algorithms(stage_plan, tensor_backend_name)

        if stage_plan.interpolation_step is None:
            _process_single_frame_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
            )
        else:
            _process_interpolated_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
            )
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(encode_queue, _ENCODE_END)


def _encoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None,
    segment_frames: int,
    resume_state: ResumeState,
    output_path: str,
    decode_queue: queue.Queue[Any],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> None:
    del decode_queue
    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    writer = None
    segment_index = len(resume_state.completed_segments) + 1
    current_segment_start = resume_state.completed_output_frames
    current_segment_input_frames = 0
    current_segment_path = ""

    try:
        while not stop_event.is_set():
            item = _queue_get(encode_queue, stop_event)
            if item is None:
                continue

            if item is _ENCODE_END:
                break

            if isinstance(item, EncodedFrame):
                if writer is None:
                    current_segment_path = manifest.segment_path(segment_index, extension)
                    writer = ffmpeg.open_rawvideo_encoder(
                        output_path=current_segment_path,
                        width=width,
                        height=height,
                        fps=fps,
                        output_fps=output_fps,
                        encode_config=encode_config,
                        progress_callback=_make_segment_progress_callback(
                            current_segment_start,
                            encode_progress_callback,
                        ),
                    )
                writer.write_frame(item.frame)
                current_segment_input_frames += 1
                continue

            if isinstance(item, SegmentBoundary):
                if writer is None:
                    continue
                if current_segment_input_frames < segment_frames:
                    continue

                writer.close()
                segment_output_frames = _resolve_segment_output_frame_count(
                    ffmpeg,
                    writer,
                    current_segment_path,
                    fallback_frame_count=current_segment_input_frames,
                )
                writer = None
                manifest.record_segment(
                    signature,
                    index=segment_index,
                    path=current_segment_path,
                    start_output_frame=current_segment_start,
                    end_output_frame=current_segment_start + segment_output_frames - 1,
                    frame_count=segment_output_frames,
                    next_source_frame=item.next_source_frame,
                )
                segment_index += 1
                current_segment_start += segment_output_frames
                current_segment_input_frames = 0
                current_segment_path = ""
                continue

            if isinstance(item, StreamEnd):
                if writer is not None and current_segment_input_frames > 0:
                    writer.close()
                    segment_output_frames = _resolve_segment_output_frame_count(
                        ffmpeg,
                        writer,
                        current_segment_path,
                        fallback_frame_count=current_segment_input_frames,
                    )
                    writer = None
                    manifest.record_segment(
                        signature,
                        index=segment_index,
                        path=current_segment_path,
                        start_output_frame=current_segment_start,
                        end_output_frame=current_segment_start + segment_output_frames - 1,
                        frame_count=segment_output_frames,
                        next_source_frame=item.next_source_frame,
                    )
                break
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # pragma: no cover - cleanup best effort
                pass


def _make_segment_progress_callback(
    segment_start_frame: int,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> Callable[[dict[str, Any]], None] | None:
    if encode_progress_callback is None:
        return None

    def callback(progress: dict[str, Any]) -> None:
        encode_progress_callback(
            segment_start_frame + int(progress.get("frame") or 0),
            progress.get("fps"),
            progress.get("speed"),
            progress.get("out_time_seconds"),
            str(progress.get("progress") or ""),
        )

    return callback


def _resolve_segment_output_frame_count(
    ffmpeg: FFmpegWrapper,
    writer: Any,
    segment_path: str,
    *,
    fallback_frame_count: int,
) -> int:
    output_frame_count = int(getattr(writer, "output_frame_count", 0) or 0)
    if output_frame_count > 0:
        return output_frame_count
    return ffmpeg.get_frame_count(segment_path) or fallback_frame_count


def _initialize_algorithms(stage_plan: StagePlan, tensor_backend_name: str) -> dict[str, Any]:
    algorithms: dict[str, Any] = {
        "single": [],
        "post": [],
        "interpolation": None,
    }

    for step in stage_plan.pre_steps:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["single"].append((step, backend, algorithm))

    if stage_plan.interpolation_step is not None:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=stage_plan.interpolation_step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **stage_plan.interpolation_step["algorithm_kwargs"],
        )
        algorithms["interpolation"] = (backend, algorithm)

    for step in stage_plan.post_steps:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["post"].append((step, backend, algorithm))

    return algorithms


def _process_single_frame_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
) -> None:
    held: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames
    single_total = max(source_frames, 1)

    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue

        if item is _DECODE_END:
            break

        if not isinstance(item, DecodedFrame):
            continue

        frame = item.frame
        for step_index, (_, backend, algorithm) in enumerate(algorithms["single"]):
            frame = _run_single_frame_algorithm(backend, algorithm, frame)
            progress_callbacks[step_index](item.source_index + 1, single_total)

        if held is None:
            held = (item.source_index, frame)
            continue

        held_source_index, held_frame = held
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held_frame),
            stop_event,
        )
        output_index += 1
        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        held = (item.source_index, frame)

    if held is not None:
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held[1]),
            stop_event,
        )
        output_index += 1

    _queue_put(
        encode_queue,
        StreamEnd(next_source_frame=source_frames),
        stop_event,
    )
    _queue_put(encode_queue, _ENCODE_END, stop_event)
    del stage_plan


def _process_interpolated_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
) -> None:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        raise RuntimeError("Interpolation stage is required for interpolated processing.")

    pre_count = len(stage_plan.pre_steps)
    interpolation_callback = progress_callbacks[pre_count]
    post_callbacks = progress_callbacks[pre_count + 1 :]
    interpolation_backend, interpolation_algorithm = algorithms["interpolation"]
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or settings.RIFE_DEFAULT_MULTI)

    previous: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames
    total_pairs = max(source_frames - 1, 1)

    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue

        if item is _DECODE_END:
            break

        if not isinstance(item, DecodedFrame):
            continue

        current_frame = item.frame
        for step_index, (_, backend, algorithm) in enumerate(algorithms["single"]):
            current_frame = _run_single_frame_algorithm(backend, algorithm, current_frame)
            progress_callbacks[step_index](item.source_index + 1, max(source_frames, 1))

        if previous is None:
            previous = (item.source_index, current_frame)
            continue

        prev_source_index, prev_frame = previous
        interpolation_callback(prev_source_index + 1, total_pairs)

        group_frames = [prev_frame]
        prev_tensor = interpolation_backend.numpy_to_tensor(prev_frame)
        current_tensor = interpolation_backend.numpy_to_tensor(current_frame)
        for mid_index in range(1, multi):
            timestep = mid_index / multi
            mid_tensor = interpolation_algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
            group_frames.append(interpolation_backend.tensor_to_numpy(mid_tensor))

        for frame in group_frames:
            processed_output = frame
            for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
                processed_output = _run_single_frame_algorithm(backend, algorithm, processed_output)
                post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
            _queue_put(
                encode_queue,
                EncodedFrame(output_index=output_index, frame=processed_output),
                stop_event,
            )
            output_index += 1

        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        previous = (item.source_index, current_frame)

    if previous is not None:
        final_frame = previous[1]
        for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
            final_frame = _run_single_frame_algorithm(backend, algorithm, final_frame)
            post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=final_frame),
            stop_event,
        )
        output_index += 1

    _queue_put(
        encode_queue,
        StreamEnd(next_source_frame=source_frames),
        stop_event,
    )
    _queue_put(encode_queue, _ENCODE_END, stop_event)


def _run_single_frame_algorithm(backend: Any, algorithm: Any, frame: np.ndarray) -> np.ndarray:
    tensor = backend.numpy_to_tensor(frame)
    processed = algorithm.process_frame(tensor)
    return backend.tensor_to_numpy(processed)


def _queue_put(target_queue: queue.Queue[Any], item: Any, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            target_queue.put(item, timeout=0.1)
            return
        except queue.Full:
            continue


def _queue_put_nowait(target_queue: queue.Queue[Any], item: Any) -> None:
    try:
        target_queue.put_nowait(item)
    except queue.Full:
        pass


def _queue_get(source_queue: queue.Queue[Any], stop_event: threading.Event) -> Any | None:
    while not stop_event.is_set():
        try:
            return source_queue.get(timeout=0.1)
        except queue.Empty:
            continue
    return None


def _finalize_segmented_output(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    completed_output_frames: int,
    total_output_frames: int,
    strict_total_frames: bool,
) -> str:
    del signature
    completed_segments = manifest.read_completed_segments()
    segment_paths = [str(manifest.sidecar_dir / record.path) for record in completed_segments]
    if strict_total_frames and completed_output_frames != total_output_frames:
        raise RuntimeError(
            f"Temporary segments are incomplete: expected {total_output_frames} output frames, "
            f"got {completed_output_frames}."
        )
    if not segment_paths:
        raise RuntimeError("No completed temporary segments were found for finalization.")

    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    concat_path = manifest.concat_temp_path(extension)
    ffmpeg.concat_videos(segment_paths, concat_path)

    keep_audio = bool(encode_config.get("keepAudio", True))
    if keep_audio and ffmpeg.has_audio(input_path):
        audio_path = ffmpeg.extract_audio(input_path, str(manifest.sidecar_dir / "source_audio.aac"))
        if audio_path:
            final_output = ffmpeg.merge_audio(concat_path, audio_path, output_path)
            Path(audio_path).unlink(missing_ok=True)
            Path(concat_path).unlink(missing_ok=True)
            return final_output

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    os.replace(concat_path, output_path)
    return output_path
