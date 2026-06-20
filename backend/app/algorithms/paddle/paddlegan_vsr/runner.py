"""PaddleGAN VSR runner entry point.

The heavy Paddle model imports stay behind this module so normal environment
checks and ONNX-only runs do not import Paddle unless the user selects a
PaddleGAN VSR algorithm.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.weights import (
    PADDLEGAN_VSR_SPECS,
    ensure_weight_file,
    get_spec,
)


class PaddleGanVsrRunner:
    """Runs one PaddleGAN video super-resolution model over an RGB frame sequence."""

    def __init__(self, *, model_id: str, num_frames: int, auto_download_weights: bool):
        self.model_id = model_id
        self.spec = get_spec(model_id)
        self.num_frames = max(1, int(num_frames or self.spec.default_num_frames))
        self.auto_download_weights = auto_download_weights
        self._paddle = None
        self._model = None

    def process_frames(self, input_frames: Sequence[np.ndarray]) -> list[np.ndarray]:
        if not input_frames:
            return []
        model = self._ensure_model()
        if self.spec.sequence_mode == "window":
            return self._process_window_model(model, input_frames)
        return self._process_recurrent_model(model, input_frames)

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        paddle = self._ensure_paddle()
        model = _build_model(self.model_id)
        weight_path = ensure_weight_file(self.model_id, auto_download=self.auto_download_weights)
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

    def _process_recurrent_model(self, model, input_frames: Sequence[np.ndarray]) -> list[np.ndarray]:
        paddle = self._ensure_paddle()
        output_frames: list[np.ndarray] = []
        with paddle.no_grad():
            for start in range(0, len(input_frames), self.num_frames):
                chunk = list(input_frames[start : start + self.num_frames])
                tensor = self._frames_to_tensor(chunk)
                output = model(tensor)
                if isinstance(output, (list, tuple)):
                    output = output[-1]
                output_frames.extend(_sequence_tensor_to_frames(output))
        return output_frames

    def _process_window_model(self, model, input_frames: Sequence[np.ndarray]) -> list[np.ndarray]:
        paddle = self._ensure_paddle()
        output_frames: list[np.ndarray] = []
        with paddle.no_grad():
            for index in range(len(input_frames)):
                neighbors = [input_frames[i] for i in _edvr_neighbor_indexes(index, len(input_frames))]
                tensor = self._frames_to_tensor(neighbors)
                output = model(tensor)
                output_frames.extend(_image_tensor_to_frames(output))
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
