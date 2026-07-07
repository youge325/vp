"""PaddleGAN VSR runner entry point.

The heavy Paddle model imports stay behind this module so normal environment
checks and ONNX-only runs do not import Paddle unless the user selects a
PaddleGAN VSR algorithm.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Sequence

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.weights import (
    PADDLEGAN_VSR_SPECS,
    ensure_paddlegan_vsr_weights,
    get_spec,
)

TRACE_ENV_VAR = "VP_PADDLEGAN_VSR_TRACE_PATH"


class PaddleGanVsrRunner:
    """Runs one PaddleGAN video super-resolution model over an RGB frame sequence."""

    def __init__(self, *, model_id: str, num_frames: int):
        self.model_id = model_id
        self.spec = get_spec(model_id)
        self.num_frames = max(1, int(num_frames or self.spec.default_num_frames))
        self._paddle = None
        self._model = None

    def process_frames(
        self,
        input_frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        if not input_frames:
            return []
        trace_path = _trace_path()
        trace_chunks: list[dict[str, Any]] | None = [] if trace_path else None
        trace_started_at = time.time()
        if trace_path:
            _reset_paddle_peak(self._ensure_paddle())

        model = self._ensure_model()
        if self.spec.sequence_mode == "window":
            output_frames = self._process_window_model(
                model,
                input_frames,
                progress_callback=progress_callback,
                trace_chunks=trace_chunks,
            )
        else:
            output_frames = self._process_recurrent_model(
                model,
                input_frames,
                progress_callback=progress_callback,
                trace_chunks=trace_chunks,
            )
        if trace_path:
            _write_trace(
                trace_path,
                {
                    "event": "process_frames",
                    "modelId": self.model_id,
                    "sequenceMode": self.spec.sequence_mode,
                    "configuredNumFrames": self.num_frames,
                    "inputFrameCount": len(input_frames),
                    "outputFrameCount": len(output_frames),
                    "chunks": trace_chunks or [],
                    "elapsedSeconds": round(time.time() - trace_started_at, 6),
                    **_paddle_memory_snapshot(self._ensure_paddle()),
                },
            )
        return output_frames

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        paddle = self._ensure_paddle()
        model = _build_model(self.model_id)
        weight_path = ensure_paddlegan_vsr_weights(self.model_id)
        state = paddle.load(str(weight_path))
        if isinstance(state, dict) and "generator" in state:
            state = state["generator"]
        model.set_dict(state)
        model.eval()
        self._model = model
        return model

    def _ensure_paddle(self):
        if self._paddle is not None:
            return self._paddle
        import paddle

        if paddle.device.is_compiled_with_cuda():
            paddle.set_device("gpu")
        self._paddle = paddle
        return paddle

    def _process_recurrent_model(
        self,
        model,
        input_frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        trace_chunks: list[dict[str, Any]] | None = None,
    ) -> list[np.ndarray]:
        paddle = self._ensure_paddle()
        output_frames: list[np.ndarray] = []
        total = len(input_frames)
        with paddle.no_grad():
            for start in range(0, len(input_frames), self.num_frames):
                chunk = list(input_frames[start : start + self.num_frames])
                tensor = self._frames_to_tensor(chunk)
                output = model(tensor)
                if isinstance(output, (list, tuple)):
                    output = output[-1]
                if trace_chunks is not None:
                    _sync_paddle(paddle)
                    trace_chunks.append(
                        {
                            "chunkFrameCount": len(chunk),
                            "inputShape": _shape_list(tensor),
                            "outputShape": _shape_list(output),
                        }
                    )
                output_frames.extend(_sequence_tensor_to_frames(output))
                if progress_callback is not None:
                    progress_callback(min(len(output_frames), total), total)
        return output_frames

    def _process_window_model(
        self,
        model,
        input_frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        trace_chunks: list[dict[str, Any]] | None = None,
    ) -> list[np.ndarray]:
        paddle = self._ensure_paddle()
        output_frames: list[np.ndarray] = []
        total = len(input_frames)
        with paddle.no_grad():
            for index in range(len(input_frames)):
                neighbors = [input_frames[i] for i in _edvr_neighbor_indexes(index, len(input_frames))]
                tensor = self._frames_to_tensor(neighbors)
                output = model(tensor)
                if trace_chunks is not None:
                    _sync_paddle(paddle)
                    trace_chunks.append(
                        {
                            "chunkFrameCount": len(neighbors),
                            "inputShape": _shape_list(tensor),
                            "outputShape": _shape_list(output),
                        }
                    )
                output_frames.extend(_image_tensor_to_frames(output))
                if progress_callback is not None:
                    progress_callback(min(len(output_frames), total), total)
        return output_frames

    def _frames_to_tensor(self, frames: Sequence[np.ndarray]):
        paddle = self._ensure_paddle()
        array = np.stack([np.asarray(frame, dtype=np.float32) / 255.0 for frame in frames], axis=0)
        array = np.transpose(array, (0, 3, 1, 2)).astype("float32", copy=False)
        array = np.expand_dims(array, axis=0)
        return paddle.to_tensor(array)


def _build_model(model_id: str):
    if model_id not in PADDLEGAN_VSR_SPECS:
        get_spec(model_id)

    if model_id == "edvr":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.edvr import EDVRNet

        return EDVRNet(nf=128, back_RBs=40)
    if model_id == "basicvsr":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.basicvsr import BasicVSRNet

        return BasicVSRNet()
    if model_id == "iconvsr":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.iconvsr import IconVSR

        return IconVSR()
    if model_id == "basicvsr-plus-plus":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.basicvsr_plus_plus import (
            BasicVSRPlusPlus,
        )

        return BasicVSRPlusPlus()
    if model_id == "ppmsvsr":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.msvsr import MSVSR

        return MSVSR()
    if model_id == "ppmsvsr-large":
        from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.msvsr import MSVSR

        return MSVSR(
            mid_channels=64,
            num_init_blocks=5,
            num_blocks=7,
            num_reconstruction_blocks=5,
            only_last=False,
            use_tiny_spynet=False,
            deform_groups=8,
            aux_reconstruction_blocks=2,
        )
    get_spec(model_id)


def _sequence_tensor_to_frames(tensor) -> list[np.ndarray]:
    array = tensor.numpy()
    if array.ndim != 5:
        raise RuntimeError(f"PaddleGAN recurrent VSR output must be 5D, got shape {array.shape}.")
    return [_chw_float_to_rgb_uint8(array[0, index]) for index in range(array.shape[1])]


def _image_tensor_to_frames(tensor) -> list[np.ndarray]:
    array = tensor.numpy()
    if array.ndim != 4:
        raise RuntimeError(f"PaddleGAN EDVR output must be 4D, got shape {array.shape}.")
    return [_chw_float_to_rgb_uint8(array[index]) for index in range(array.shape[0])]


def _chw_float_to_rgb_uint8(chw: np.ndarray) -> np.ndarray:
    image = np.clip(chw, 0.0, 1.0) * 255.0
    image = image.round().astype(np.uint8)
    return np.transpose(image, (1, 2, 0))


def _edvr_neighbor_indexes(index: int, length: int, window_size: int = 5) -> list[int]:
    if length <= 0:
        return []
    radius = window_size // 2
    return [min(max(index + offset, 0), length - 1) for offset in range(-radius, radius + 1)]


def _trace_path() -> Path | None:
    value = os.environ.get(TRACE_ENV_VAR)
    if not value:
        return None
    return Path(value)


def _write_trace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _shape_list(value: Any) -> list[int] | None:
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    return [int(dim) for dim in shape]


def _reset_paddle_peak(paddle: Any) -> None:
    for name in ("reset_max_memory_reserved", "reset_max_memory_allocated"):
        fn = getattr(getattr(paddle.device, "cuda", None), name, None)
        if callable(fn):
            fn()


def _paddle_memory_snapshot(paddle: Any) -> dict[str, int | None]:
    _sync_paddle(paddle)

    def call(name: str) -> int | None:
        fn = getattr(getattr(paddle.device, "cuda", None), name, None)
        if not callable(fn):
            return None
        return int(fn())

    return {
        "maxMemoryReservedBytes": call("max_memory_reserved"),
        "maxMemoryAllocatedBytes": call("max_memory_allocated"),
    }


def _sync_paddle(paddle: Any) -> None:
    device_sync = getattr(getattr(paddle, "device", None), "synchronize", None)
    if callable(device_sync):
        device_sync()
        return
    cuda_sync = getattr(getattr(paddle.device, "cuda", None), "synchronize", None)
    if callable(cuda_sync):
        cuda_sync()
