"""Paddle Inference TensorRT predictor and static-model cache."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile
from typing import Any, NamedTuple, Sequence

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.tensor_codec import as_numpy, shape_list
from app.protocol.process_markers import TENSORRT_LOG_PREFIX
from app.utils.logger import get_logger

logger = get_logger(__name__)


class _PredictorBinding(NamedTuple):
    predictor: Any
    input_name: str
    output_names: list[str]


class _TensorRtPredictorCache:
    """Create and retain shape-specific Paddle TensorRT predictors."""

    def __init__(
        self,
        *,
        paddle: Any,
        model: Any,
        model_id: str,
        sequence_mode: str,
        num_frames: int,
    ):
        if num_frames < 1:
            raise ValueError("PaddleGAN TensorRT num_frames must be at least 1.")
        self.paddle = paddle
        self.model = model
        self.model_id = model_id
        self.runtime_frame_count = 5 if sequence_mode == "window" else num_frames
        self._entries: dict[tuple[int, int, int], _PredictorBinding] = {}
        self._logged_reuse_keys: set[tuple[int, int, int]] = set()

    def ensure(self, input_shape: list[int]) -> _PredictorBinding:
        _, _, _, height, width = input_shape
        key = (self.runtime_frame_count, height, width)
        shape = [1, self.runtime_frame_count, 3, height, width]
        shape_text = _format_shape(shape)
        if key in self._entries:
            if key not in self._logged_reuse_keys:
                _emit_tensorrt_log(f"REUSE PaddleGAN {self.model_id} shape={shape_text}")
                self._logged_reuse_keys.add(key)
            return self._entries[key]

        prefix = _tensorrt_model_prefix(
            self.model_id,
            max_frames=self.runtime_frame_count,
            height=height,
            width=width,
        )
        model_file, params_file = self._ensure_static_model(prefix, shape, shape_text)
        cache_dir = prefix.parent / "trt-cache"
        _emit_tensorrt_log(f"CACHE dir={cache_dir}")
        entry = _create_tensorrt_predictor(
            paddle=self.paddle,
            model_file=model_file,
            params_file=params_file,
            input_name="input",
            min_shape=shape,
            max_shape=shape,
            optim_shape=shape,
            cache_dir=cache_dir,
        )
        _emit_tensorrt_log(f"READY outputs={','.join(entry.output_names)}")
        self._entries[key] = entry
        return entry

    def _ensure_static_model(self, prefix: Path, shape: list[int], shape_text: str) -> tuple[Path, Path]:
        legacy_model_file = Path(f"{prefix}.pdmodel")
        pir_model_file = Path(f"{prefix}.json")
        params_file = Path(f"{prefix}.pdiparams")
        model_file = legacy_model_file if legacy_model_file.is_file() else pir_model_file
        if not model_file.is_file() or not params_file.is_file():
            _emit_tensorrt_log(f"BUILD PaddleGAN {self.model_id} shape={shape_text}")
            prefix.parent.mkdir(parents=True, exist_ok=True)
            input_spec = [self.paddle.static.InputSpec(shape=shape, dtype="float32", name="input")]
            static_model = self.paddle.jit.to_static(self.model, input_spec=input_spec, full_graph=True)
            self.paddle.jit.save(static_model, str(prefix))
            model_file = legacy_model_file if legacy_model_file.is_file() else pir_model_file
            _emit_tensorrt_log(f"SAVE static_model={model_file} params={params_file}")
        else:
            _emit_tensorrt_log(f"LOAD static_model={model_file} params={params_file}")
        return model_file, params_file


class PaddleGanTensorRtPredictor:
    """Pad variable recurrent chunks and invoke a cached fixed-shape predictor."""

    def __init__(
        self,
        *,
        paddle: Any,
        model: Any,
        model_id: str,
        sequence_mode: str,
        num_frames: int,
    ):
        self._cache = _TensorRtPredictorCache(
            paddle=paddle,
            model=model,
            model_id=model_id,
            sequence_mode=sequence_mode,
            num_frames=num_frames,
        )

    def run(self, tensor: Any) -> np.ndarray:
        shape = shape_list(tensor)
        if shape is None or len(shape) != 5:
            raise RuntimeError(f"PaddleGAN TensorRT input must be 5D, got shape {shape}.")
        binding = self._cache.ensure(shape)
        original_frame_count = shape[1]
        runtime_frame_count = self._cache.runtime_frame_count
        if original_frame_count > runtime_frame_count:
            raise RuntimeError(
                f"PaddleGAN TensorRT input has {original_frame_count} frames, "
                f"but the predictor was built for {runtime_frame_count}."
            )
        array = as_numpy(tensor).astype("float32", copy=False)
        if original_frame_count < runtime_frame_count:
            pad = np.repeat(array[:, -1:, :, :, :], runtime_frame_count - original_frame_count, axis=1)
            array = np.concatenate([array, pad], axis=1)
        input_handle = binding.predictor.get_input_handle(binding.input_name)
        input_handle.copy_from_cpu(array)
        binding.predictor.run()
        output_handle = binding.predictor.get_output_handle(binding.output_names[-1])
        output = np.asarray(output_handle.copy_to_cpu(), dtype=np.float32)
        if output.ndim == 5 and original_frame_count < runtime_frame_count:
            output = output[:, :original_frame_count, :, :, :]
        return output


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
) -> _PredictorBinding:
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
    return _PredictorBinding(predictor, input_names[0], output_names)


def _emit_tensorrt_log(message: str) -> None:
    logger.info("%s TensorRT %s", TENSORRT_LOG_PREFIX, message)


def _format_shape(shape: Sequence[int]) -> str:
    return "x".join(str(int(dim)) for dim in shape)


__all__ = ["PaddleGanTensorRtPredictor"]
