"""Tests for FrameFilterChainAlgorithm."""

from __future__ import annotations

import numpy as np
import pytest

from app.processing.frame_filters import FrameFilterChainAlgorithm


class _FakeTensorBackend:
    """A minimal tensor backend that treats numpy arrays as their own tensors."""

    def numpy_to_tensor(self, array: np.ndarray) -> np.ndarray:
        return array

    def tensor_to_numpy(self, tensor: np.ndarray) -> np.ndarray:
        return tensor

    def get_name(self) -> str:
        return "fake"


class _FakePyTorchBackend(_FakeTensorBackend):
    def get_name(self) -> str:
        return "pytorch"


def _make_algorithm(filters: list[dict]) -> FrameFilterChainAlgorithm:
    return FrameFilterChainAlgorithm(tensor_backend=_FakeTensorBackend(), filters=filters)


def _make_pytorch_algorithm(filters: list[dict]) -> FrameFilterChainAlgorithm:
    return FrameFilterChainAlgorithm(tensor_backend=_FakePyTorchBackend(), filters=filters)


def test_validate_unknown_kind_raises():
    with pytest.raises(ValueError, match="Unknown filter kind"):
        _make_algorithm([{"kind": "unknown", "enabled": True, "params": {}}])


def test_validate_missing_params_raises():
    with pytest.raises(ValueError, match="missing params"):
        _make_algorithm([{"kind": "scale", "enabled": True}])


def test_anime_cleanup_filter_runs_without_loading_opencv(monkeypatch: pytest.MonkeyPatch):
    import app.processing.frame_filter_handlers as handlers

    monkeypatch.setattr(handlers, "import_cv2", lambda: (_ for _ in ()).throw(AssertionError("cv2 loaded")))
    frame = np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3)
    algo = _make_algorithm(
        [
            {
                "kind": "anime_cleanup",
                "enabled": True,
                "params": {"profile": "clean-lines", "denoise": 0, "edgeBoost": 0},
            }
        ]
    )

    out = algo.process_frame(frame)

    assert out is frame


def test_anime_cleanup_filter_forces_pytorch_cpu_fallback():
    algo = _make_pytorch_algorithm(
        [
            {
                "kind": "anime_cleanup",
                "enabled": True,
                "params": {"profile": "clean-lines", "denoise": 15, "edgeBoost": 30},
            }
        ]
    )

    assert algo.can_process_tensor(_FakePyTorchBackend()) is False


def test_scale_factor_changes_resolution():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "scale",
                "enabled": True,
                "params": {"mode": "factor", "factor": 0.5, "interpolation": "lanczos4"},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (540, 960, 3)


def test_scale_resolution_target():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "scale",
                "enabled": True,
                "params": {"mode": "resolution", "width": 1280, "height": 720, "interpolation": "cubic"},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (720, 1280, 3)


def test_scale_factor_one_is_noop():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "scale",
                "enabled": True,
                "params": {"mode": "factor", "factor": 1.0, "interpolation": "lanczos4"},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == frame.shape
    assert np.array_equal(out, frame)


def test_crop_changes_dims():
    frame = np.ones((1080, 1920, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "crop",
                "enabled": True,
                "params": {"x": 100, "y": 50, "width": 200, "height": 150},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (150, 200, 3)


def test_crop_clamps_to_bounds():
    frame = np.ones((100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "crop",
                "enabled": True,
                "params": {"x": 50, "y": 50, "width": 200, "height": 200},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (50, 50, 3)


def test_pad_increases_dims():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "pad",
                "enabled": True,
                "params": {"top": 10, "bottom": 10, "left": 20, "right": 20, "color": "#ff0000"},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (120, 140, 3)
    # top-left padded pixel should be red (RGB)
    assert np.all(out[0, 0] == [255, 0, 0])


def test_pad_zero_is_noop():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "pad",
                "enabled": True,
                "params": {"top": 0, "bottom": 0, "left": 0, "right": 0, "color": "#000000"},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == frame.shape
    assert np.array_equal(out, frame)


def test_sharpen_changes_pixels():
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    algo = _make_algorithm(
        [
            {
                "kind": "sharpen",
                "enabled": True,
                "params": {"amount": 1.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    # Sharpening a uniform field should still be uniform (uint8 clamped)
    assert out.shape == frame.shape


def test_sharpen_zero_amount_is_noop():
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "sharpen",
                "enabled": True,
                "params": {"amount": 0.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert np.array_equal(out, frame)


def test_denoise_preserves_shape():
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "denoise",
                "enabled": True,
                "params": {"strength": 10, "colorStrength": 10},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == frame.shape


def test_denoise_zero_is_noop():
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "denoise",
                "enabled": True,
                "params": {"strength": 0, "colorStrength": 0},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert np.array_equal(out, frame)


def test_color_brightness_changes_mean():
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    algo = _make_algorithm(
        [
            {
                "kind": "color",
                "enabled": True,
                "params": {"brightness": 0.5, "contrast": 1.0, "saturation": 1.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert out.mean() > 128


def test_color_contrast_zero_flattens():
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "color",
                "enabled": True,
                "params": {"brightness": 0.0, "contrast": 0.0, "saturation": 1.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    # contrast=0 should map everything to the same gray value
    assert out.std() < 1.0


def test_color_no_change_is_noop():
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    algo = _make_algorithm(
        [
            {
                "kind": "color",
                "enabled": True,
                "params": {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert np.array_equal(out, frame)


def test_disabled_step_is_skipped():
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    algo = _make_algorithm(
        [
            {
                "kind": "color",
                "enabled": False,
                "params": {"brightness": 0.5, "contrast": 1.0, "saturation": 1.0},
            }
        ]
    )
    out = algo.process_frame(frame)
    assert np.array_equal(out, frame)


def test_multiple_filters_applied_in_order():
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    algo = _make_algorithm(
        [
            {
                "kind": "scale",
                "enabled": True,
                "params": {"mode": "factor", "factor": 0.5, "interpolation": "area"},
            },
            {
                "kind": "pad",
                "enabled": True,
                "params": {"top": 10, "bottom": 10, "left": 10, "right": 10, "color": "#ffffff"},
            },
        ]
    )
    out = algo.process_frame(frame)
    assert out.shape == (70, 70, 3)


def test_can_process_tensor_accepts_supported_pytorch_filters():
    algo = _make_pytorch_algorithm(
        [
            {"kind": "scale", "enabled": True, "params": {"mode": "factor", "factor": 0.5}},
            {"kind": "crop", "enabled": True, "params": {"x": 0, "y": 0, "width": 4, "height": 4}},
            {"kind": "pad", "enabled": True, "params": {"top": 1, "bottom": 1, "left": 1, "right": 1}},
            {"kind": "sharpen", "enabled": True, "params": {"amount": 0.0}},
            {"kind": "color", "enabled": True, "params": {"brightness": 0.1, "contrast": 1.0}},
        ]
    )

    assert algo.can_process_tensor(_FakePyTorchBackend()) is True


def test_can_process_tensor_rejects_nonzero_denoise():
    algo = _make_pytorch_algorithm(
        [
            {"kind": "denoise", "enabled": True, "params": {"strength": 10, "colorStrength": 10}},
        ]
    )

    assert algo.can_process_tensor(_FakePyTorchBackend()) is False
