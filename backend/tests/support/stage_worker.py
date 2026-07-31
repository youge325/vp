from __future__ import annotations

import io

import numpy as np

from app.planning.processing_steps import ProcessingStep
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.stage_worker_config import build_stage_worker_step


class IdentityBackend:
    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, np.ndarray]:
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, np.ndarray]) -> np.ndarray:
        return tensor["tensor"].copy()


class IncrementAlgorithm:
    def process_frame(self, tensor: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        return {"tensor": tensor["tensor"] + 1}


class MidpointAlgorithm:
    def process_frame_pair(
        self,
        frame0: dict[str, np.ndarray],
        frame1: dict[str, np.ndarray],
        *,
        timestep: float = 0.5,
    ) -> dict[str, np.ndarray]:
        previous = frame0["tensor"].astype(np.float32)
        current = frame1["tensor"].astype(np.float32)
        return {"tensor": np.rint(previous + (current - previous) * timestep).astype(np.uint8)}


class ProgressSequenceAlgorithm:
    def process_frame_sequence(self, frames: list[np.ndarray], **kwargs: object) -> list[np.ndarray]:
        progress_callback = kwargs.get("progress_callback")
        if callable(progress_callback):
            progress_callback(len(frames), len(frames))
        return [frame + 10 for frame in frames]


def frame(value: int, *, height: int = 1, width: int = 1) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def stream_of(frames: list[np.ndarray]) -> io.BytesIO:
    return io.BytesIO(b"".join(np.ascontiguousarray(item).tobytes() for item in frames))


def frames_from_bytes(
    raw: bytes,
    *,
    count: int,
    height: int = 1,
    width: int = 1,
) -> list[np.ndarray]:
    frame_bytes = height * width * 3
    assert len(raw) == count * frame_bytes
    return [
        np.frombuffer(raw[index * frame_bytes : (index + 1) * frame_bytes], dtype=np.uint8).reshape((height, width, 3))
        for index in range(count)
    ]


def make_stage_worker_config(
    step: ProcessingStep,
    *,
    input_frame_count: int = 2,
) -> StageWorkerConfig:
    payload = step.to_jsonable()
    kwargs = payload["algorithm_kwargs"]
    kwargs.pop("tensor_backend", None)
    if step.algorithm_type == "frame_interpolation":
        kwargs |= {
            "algorithm": kwargs.get("algorithm", "rife"),
            "model_version": kwargs.get("model_version", "4.25"),
            "scale": kwargs.get("scale", 1.0),
            "fp16": kwargs.get("fp16", False),
            "onnx_model": kwargs.get("onnx_model"),
            "engine": kwargs.get("engine", "cuda"),
        }
    elif step.algorithm_type == "super_resolution":
        kwargs |= {
            "scale_factor": kwargs.get("scale_factor", 1.0),
            "sr_algorithm": kwargs.get("sr_algorithm", "placeholder"),
            "onnx_model": kwargs.get("onnx_model"),
            "engine": kwargs.get("engine", "cuda"),
            "num_frames": kwargs.get("num_frames", 10),
        }
    normalized_step = ProcessingStep(
        algorithm_type=step.algorithm_type,
        algorithm_kwargs=kwargs,
        stage_name=step.stage_name,
    )
    output_frame_count = input_frame_count
    if step.algorithm_type == "frame_interpolation" and input_frame_count > 0:
        output_frame_count = 1 + (input_frame_count - 1) * int(kwargs["multi"])
    tensor_backend_name = None
    if step.algorithm_type != "frame_filter_chain":
        tensor_backend_name = "paddle" if normalized_step.descriptor.supported_backends == {"paddle"} else "onnx"
    return StageWorkerConfig(
        stage=build_stage_worker_step(normalized_step),
        stage_index=1,
        stage_total=1,
        stage_name=step.stage_name,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        input_frame_count=input_frame_count,
        tensor_backend_name=tensor_backend_name,
        output_frame_count=output_frame_count,
    )
