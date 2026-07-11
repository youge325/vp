"""Anime cleanup filter behavior."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest


def test_anime_cleanup_module_exists() -> None:
    assert importlib.util.find_spec("app.processing.anime_cleanup") is not None


def test_profile_specs_expose_stable_defaults_and_curves() -> None:
    from app.processing.anime_cleanup import _PROFILE_SPECS

    assert _PROFILE_SPECS == {
        "clean-lines": {
            "default_denoise": 15,
            "default_edge_boost": 30,
            "median_size": 3,
            "denoise_gain": 1.0,
            "edge_radius": 1.0,
            "edge_gain": 1.0,
            "edge_threshold": 2,
        },
        "thin-outline": {
            "default_denoise": 8,
            "default_edge_boost": 45,
            "median_size": 3,
            "denoise_gain": 0.6,
            "edge_radius": 0.6,
            "edge_gain": 1.25,
            "edge_threshold": 1,
        },
        "balanced-cel": {
            "default_denoise": 25,
            "default_edge_boost": 20,
            "median_size": 5,
            "denoise_gain": 0.85,
            "edge_radius": 1.4,
            "edge_gain": 0.8,
            "edge_threshold": 3,
        },
    }


@pytest.mark.parametrize(
    ("profile", "denoise", "edge_boost"),
    [
        ("clean-lines", 15, 30),
        ("thin-outline", 8, 45),
        ("balanced-cel", 25, 20),
    ],
)
def test_missing_strengths_use_profile_defaults(profile: str, denoise: int, edge_boost: int) -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    frame = np.arange(12 * 12 * 3, dtype=np.uint8).reshape(12, 12, 3)

    implicit = apply_anime_cleanup(frame, profile=profile, denoise=None, edge_boost=None)
    explicit = apply_anime_cleanup(frame, profile=profile, denoise=denoise, edge_boost=edge_boost)

    np.testing.assert_array_equal(implicit, explicit)


def test_zero_strength_is_an_identity_operation() -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    frame = np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3)

    result = apply_anime_cleanup(frame, profile="clean-lines", denoise=0, edge_boost=0)

    assert result is frame


def test_denoise_reduces_pixel_variance_without_changing_contract() -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    rng = np.random.default_rng(7)
    frame = rng.integers(80, 176, size=(32, 32, 3), dtype=np.uint8)

    result = apply_anime_cleanup(frame, profile="balanced-cel", denoise=100, edge_boost=0)

    assert result.shape == frame.shape
    assert result.dtype == np.uint8
    assert result.flags.c_contiguous
    assert float(result.var()) < float(frame.var())


def test_edge_boost_increases_contrast_across_a_soft_boundary() -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    soft_edge = np.array([80] * 13 + [90, 110, 146, 166] + [176] * 15, dtype=np.uint8)
    frame = np.repeat(soft_edge[np.newaxis, :, np.newaxis], 24, axis=0)
    frame = np.repeat(frame, 3, axis=2)

    result = apply_anime_cleanup(frame, profile="thin-outline", denoise=0, edge_boost=100)

    original_delta = int(frame[:, 17].mean()) - int(frame[:, 12].mean())
    boosted_delta = int(result[:, 17].mean()) - int(result[:, 12].mean())
    assert boosted_delta > original_delta


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"profile": "unknown", "denoise": 10, "edge_boost": 10}, "Unknown Anime cleanup profile"),
        ({"profile": "clean-lines", "denoise": -1, "edge_boost": 10}, "denoise must be between 0 and 100"),
        ({"profile": "clean-lines", "denoise": 10, "edge_boost": 101}, "edge_boost must be between 0 and 100"),
    ],
)
def test_invalid_profile_or_strength_fails_loudly(kwargs: dict[str, object], message: str) -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match=message):
        apply_anime_cleanup(frame, **kwargs)


@pytest.mark.parametrize(
    "frame",
    [
        np.zeros((8, 8), dtype=np.uint8),
        np.zeros((8, 8, 4), dtype=np.uint8),
        np.zeros((8, 8, 3), dtype=np.float32),
    ],
)
def test_invalid_frame_contract_is_rejected(frame: np.ndarray) -> None:
    from app.processing.anime_cleanup import apply_anime_cleanup

    with pytest.raises(ValueError, match="HWC RGB uint8"):
        apply_anime_cleanup(frame, profile="clean-lines", denoise=15, edge_boost=30)
