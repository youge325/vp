"""PaddleGAN VSR runner entry point.

The heavy Paddle model imports stay behind this module so normal environment
checks and ONNX-only runs do not import Paddle unless the user selects a
PaddleGAN VSR algorithm.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.weights import ensure_paddlegan_vsr_weights, get_spec
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.protocol.process_markers import TENSORRT_LOG_PREFIX as _TENSORRT_LOG_PREFIX
from app.utils.logger import get_logger

_TRACE_ENV_VAR = "VP_PADDLEGAN_VSR_TRACE_PATH"
logger = get_logger(__name__)


class PaddleGanVsrRunner:
    """Runs one PaddleGAN video super-resolution model over an RGB frame sequence."""

    def __init__(self, *, model_id: str, num_frames: int, engine: str = "cuda"):
        self.model_id = model_id
        self.spec = get_spec(model_id)
        self.num_frames = max(1, int(num_frames or self.spec.default_num_frames))
        self.engine = (engine or "cuda").lower()
        if self.engine not in {"cuda", "tensorrt"}:
            raise ValueError(f"Unsupported PaddleGAN VSR engine: {engine!r}")
        self._paddle = None
        self._model = None
        self._trt_predictor = None

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
            batches = (
                [input_frames[i] for i in _edvr_neighbor_indexes(index, len(input_frames))]
                for index in range(len(input_frames))
            )
            output_to_frames = _image_tensor_to_frames
            select_last_output = False
        else:
            batches = (
                list(input_frames[start : start + self.num_frames])
                for start in range(0, len(input_frames), self.num_frames)
            )
            output_to_frames = _sequence_tensor_to_frames
            select_last_output = True
        output_frames = self._process_batches(
            model,
            batches,
            total=len(input_frames),
            output_to_frames=output_to_frames,
            select_last_output=select_last_output,
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

    def _process_batches(
        self,
        model: Any,
        batches: Iterable[Sequence[np.ndarray]],
        *,
        total: int,
        output_to_frames: Callable[[Any], list[np.ndarray]],
        select_last_output: bool,
        progress_callback: Callable[[int, int], None] | None,
        trace_chunks: list[dict[str, Any]] | None,
    ) -> list[np.ndarray]:
        paddle = self._ensure_paddle()
        output_frames: list[np.ndarray] = []
        with paddle.no_grad():
            for batch in batches:
                tensor = self._frames_to_tensor(batch)
                output = self._run_tensor(model, tensor)
                if select_last_output and isinstance(output, (list, tuple)):
                    output = output[-1]
                _record_chunk_trace(trace_chunks, paddle, tensor=tensor, output=output, frame_count=len(batch))
                output_frames.extend(output_to_frames(output))
                if progress_callback is not None:
                    progress_callback(min(len(output_frames), total), total)
        return output_frames

    def _run_tensor(self, model, tensor):
        if self.engine == "tensorrt":
            return self._ensure_tensorrt_predictor(model).run(tensor)
        return model(tensor)

    def _frames_to_tensor(self, frames: Sequence[np.ndarray]):
        paddle = self._ensure_paddle()
        array = np.stack([np.asarray(frame, dtype=np.float32) / 255.0 for frame in frames], axis=0)
        array = np.transpose(array, (0, 3, 1, 2)).astype("float32", copy=False)
        array = np.expand_dims(array, axis=0)
        return paddle.to_tensor(array)

    def _ensure_tensorrt_predictor(self, model):
        if self._trt_predictor is None:
            self._trt_predictor = _PaddleGanTensorRtPredictor(
                paddle=self._ensure_paddle(),
                model=model,
                model_id=self.model_id,
                sequence_mode=self.spec.sequence_mode,
                num_frames=self.num_frames,
            )
        return self._trt_predictor


class _PaddleGanTensorRtPredictor:
    def __init__(
        self,
        *,
        paddle: Any,
        model: Any,
        model_id: str,
        sequence_mode: str,
        num_frames: int,
    ):
        self.paddle = paddle
        self.model = model
        self.model_id = model_id
        self.sequence_mode = sequence_mode
        self.num_frames = max(1, int(num_frames))
        self._cache: dict[tuple[int, int, int], tuple[Any, str, list[str]]] = {}
        self._logged_reuse_keys: set[tuple[int, int, int]] = set()

    def run(self, tensor: Any) -> np.ndarray:
        shape = _shape_list(tensor)
        if shape is None or len(shape) != 5:
            raise RuntimeError(f"PaddleGAN TensorRT input must be 5D, got shape {shape}.")
        predictor, input_name, output_names = self._ensure_predictor(shape)
        original_frame_count = shape[1]
        runtime_frame_count = self._runtime_frame_count()
        if original_frame_count > runtime_frame_count:
            raise RuntimeError(
                f"PaddleGAN TensorRT input has {original_frame_count} frames, "
                f"but the predictor was built for {runtime_frame_count}."
            )
        array = _as_numpy(tensor).astype("float32", copy=False)
        if original_frame_count < runtime_frame_count:
            pad = np.repeat(array[:, -1:, :, :, :], runtime_frame_count - original_frame_count, axis=1)
            array = np.concatenate([array, pad], axis=1)
        input_handle = predictor.get_input_handle(input_name)
        input_handle.copy_from_cpu(array)
        predictor.run()
        output_handle = predictor.get_output_handle(output_names[-1])
        output = np.asarray(output_handle.copy_to_cpu(), dtype=np.float32)
        if output.ndim == 5 and original_frame_count < runtime_frame_count:
            output = output[:, :original_frame_count, :, :, :]
        return output

    def _ensure_predictor(self, shape: list[int]) -> tuple[Any, str, list[str]]:
        _, _, _, height, width = shape
        runtime_frames = self._runtime_frame_count()
        key = (runtime_frames, height, width)
        shape_text = _format_shape([1, runtime_frames, 3, height, width])
        if key in self._cache:
            if key not in self._logged_reuse_keys:
                _emit_tensorrt_log(f"REUSE PaddleGAN {self.model_id} shape={shape_text}")
                self._logged_reuse_keys.add(key)
            return self._cache[key]

        prefix = _tensorrt_model_prefix(self.model_id, max_frames=runtime_frames, height=height, width=width)
        legacy_model_file = Path(str(prefix) + ".pdmodel")
        pir_model_file = Path(str(prefix) + ".json")
        params_file = Path(str(prefix) + ".pdiparams")
        if (not legacy_model_file.is_file() and not pir_model_file.is_file()) or not params_file.is_file():
            _emit_tensorrt_log(f"BUILD PaddleGAN {self.model_id} shape={shape_text}")
            prefix.parent.mkdir(parents=True, exist_ok=True)
            input_spec = [
                self.paddle.static.InputSpec(
                    shape=[1, runtime_frames, 3, height, width],
                    dtype="float32",
                    name="input",
                )
            ]
            static_model = self.paddle.jit.to_static(self.model, input_spec=input_spec, full_graph=True)
            self.paddle.jit.save(static_model, str(prefix))
            model_file = legacy_model_file if legacy_model_file.is_file() else pir_model_file
            _emit_tensorrt_log(f"SAVE static_model={model_file} params={params_file}")
        else:
            model_file = legacy_model_file if legacy_model_file.is_file() else pir_model_file
            _emit_tensorrt_log(f"LOAD static_model={model_file} params={params_file}")

        cache_dir = prefix.parent / "trt-cache"
        _emit_tensorrt_log(f"CACHE dir={cache_dir}")
        entry = _create_tensorrt_predictor(
            paddle=self.paddle,
            model_file=model_file,
            params_file=params_file,
            input_name="input",
            min_shape=[1, runtime_frames, 3, height, width],
            max_shape=[1, runtime_frames, 3, height, width],
            optim_shape=[1, runtime_frames, 3, height, width],
            cache_dir=cache_dir,
        )
        _emit_tensorrt_log(f"READY outputs={','.join(entry[2])}")
        self._cache[key] = entry
        return entry

    def _runtime_frame_count(self) -> int:
        return 5 if self.sequence_mode == "window" else self.num_frames


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
    return _tensor_output_to_frames(
        tensor,
        expected_ndim=5,
        description="PaddleGAN recurrent VSR output",
        batch_index=0,
    )


def _image_tensor_to_frames(tensor) -> list[np.ndarray]:
    return _tensor_output_to_frames(
        tensor,
        expected_ndim=4,
        description="PaddleGAN EDVR output",
    )


def _tensor_output_to_frames(
    tensor,
    *,
    expected_ndim: int,
    description: str,
    batch_index: int | None = None,
) -> list[np.ndarray]:
    array = _as_numpy(tensor)
    if array.ndim != expected_ndim:
        raise RuntimeError(f"{description} must be {expected_ndim}D, got shape {array.shape}.")
    chw_batch = array if batch_index is None else array[batch_index]
    return [_chw_float_to_rgb_uint8(chw) for chw in chw_batch]


def _chw_float_to_rgb_uint8(chw: np.ndarray) -> np.ndarray:
    image = np.clip(chw, 0.0, 1.0) * 255.0
    image = image.round().astype(np.uint8)
    return np.transpose(image, (1, 2, 0))


def _edvr_neighbor_indexes(index: int, length: int, window_size: int = 5) -> list[int]:
    if length <= 0:
        return []
    radius = window_size // 2
    return [min(max(index + offset, 0), length - 1) for offset in range(-radius, radius + 1)]


def _as_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    numpy_fn = getattr(value, "numpy", None)
    if callable(numpy_fn):
        return numpy_fn()
    return np.asarray(value)


def _tensorrt_model_prefix(model_id: str, *, max_frames: int, height: int, width: int) -> Path:
    safe_model_id = "".join(ch if ch.isalnum() else "_" for ch in model_id)
    cache_root = Path(os.environ.get("VP_PADDLEGAN_TRT_CACHE_DIR") or Path(tempfile.gettempdir()) / "vp-paddlegan-trt")
    return cache_root / safe_model_id / f"t{max_frames}_h{height}_w{width}" / "model"


def _configure_tensorrt_config(
    config: Any,
    paddle: Any,
    *,
    input_name: str,
    min_shape: list[int],
    max_shape: list[int],
    optim_shape: list[int],
    cache_dir: str | None = None,
) -> None:
    precision = paddle.inference.PrecisionType.Float32
    config.enable_use_gpu(512, 0)
    switch_ir_optim = getattr(config, "switch_ir_optim", None)
    if callable(switch_ir_optim):
        switch_ir_optim(True)
    set_optim_cache_dir = getattr(config, "set_optim_cache_dir", None)
    if callable(set_optim_cache_dir) and cache_dir:
        set_optim_cache_dir(cache_dir)
    config.enable_tensorrt_engine(
        workspace_size=1 << 30,
        max_batch_size=1,
        min_subgraph_size=3,
        precision_mode=precision,
        use_static=True,
        use_calib_mode=False,
    )
    config.set_trt_dynamic_shape_info(
        {input_name: min_shape},
        {input_name: max_shape},
        {input_name: optim_shape},
    )
    enable_memory_optim = getattr(config, "enable_tensorrt_memory_optim", None)
    if callable(enable_memory_optim):
        enable_memory_optim()
    disable_glog = getattr(config, "disable_glog_info", None)
    if callable(disable_glog):
        disable_glog()
    tensorrt_engine_enabled = getattr(config, "tensorrt_engine_enabled", None)
    if callable(tensorrt_engine_enabled) and not tensorrt_engine_enabled():
        raise RuntimeError("Paddle Inference TensorRT engine was requested but is not enabled in Config.")


def _create_tensorrt_predictor(
    *,
    paddle: Any,
    model_file: Path,
    params_file: Path,
    input_name: str,
    min_shape: list[int],
    max_shape: list[int],
    optim_shape: list[int],
    cache_dir: Path,
) -> tuple[Any, str, list[str]]:
    config = paddle.inference.Config(str(model_file), str(params_file))
    _configure_tensorrt_config(
        config,
        paddle,
        input_name=input_name,
        min_shape=min_shape,
        max_shape=max_shape,
        optim_shape=optim_shape,
        cache_dir=str(cache_dir),
    )
    predictor = paddle.inference.create_predictor(config)
    input_names = list(predictor.get_input_names())
    output_names = list(predictor.get_output_names())
    if not input_names:
        raise RuntimeError("PaddleGAN TensorRT predictor has no inputs.")
    if not output_names:
        raise RuntimeError("PaddleGAN TensorRT predictor has no outputs.")
    return predictor, input_names[0], output_names


def _emit_tensorrt_log(message: str) -> None:
    logger.info("%s TensorRT %s", _TENSORRT_LOG_PREFIX, message)


def _format_shape(shape: Sequence[int]) -> str:
    return "x".join(str(int(dim)) for dim in shape)


def _trace_path() -> Path | None:
    value = os.environ.get(_TRACE_ENV_VAR)
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


def _record_chunk_trace(
    trace_chunks: list[dict[str, Any]] | None,
    paddle: Any,
    *,
    tensor: Any,
    output: Any,
    frame_count: int,
) -> None:
    if trace_chunks is None:
        return
    _sync_paddle(paddle)
    trace_chunks.append(
        {
            "chunkFrameCount": frame_count,
            "inputShape": _shape_list(tensor),
            "outputShape": _shape_list(output),
        }
    )


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
