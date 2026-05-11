"""Processor worker — runs algorithms between decode and encode queues.

Two flavours of the inner loop:

- ``_process_single_frame_stream`` for pipelines without interpolation
- ``_process_interpolated_stream`` for pipelines with a RIFE-style
  interpolation step that emits ``multi`` frames per source pair
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import StagePlan
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _DECODE_END,
    _ENCODE_END,
    _queue_get,
    _queue_put,
    _queue_put_nowait,
)


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


def _initialize_algorithms(stage_plan: StagePlan, tensor_backend_name: str) -> dict[str, Any]:
    algorithms: dict[str, Any] = {
        "single": [],
        "post": [],
        "interpolation": None,
    }

    # Re-use a single backend instance across all algorithms in the pipeline.
    # This avoids redundant DLL registration and repeated ``import onnxruntime``
    # when multiple steps share the same tensor backend.
    shared_backend = get_tensor_backend(tensor_backend_name)

    for step in stage_plan.pre_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["single"].append((step, shared_backend, algorithm))

    if stage_plan.interpolation_step is not None:
        algorithm = AlgorithmFactory.create(
            algorithm_type=stage_plan.interpolation_step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **stage_plan.interpolation_step["algorithm_kwargs"],
        )
        algorithms["interpolation"] = (shared_backend, algorithm)

    for step in stage_plan.post_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["post"].append((step, shared_backend, algorithm))

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
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or 2)

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
