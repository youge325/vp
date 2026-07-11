"""Frame-local cleanup tuned for animated line art."""

from __future__ import annotations

from typing import Final, TypedDict

import numpy as np
from PIL import Image, ImageFilter


class _AnimeProfileSpec(TypedDict):
    default_denoise: int
    default_edge_boost: int
    median_size: int
    denoise_gain: float
    edge_radius: float
    edge_gain: float
    edge_threshold: int


_PROFILE_SPECS: Final[dict[str, _AnimeProfileSpec]] = {
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


def _validate_strength(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be between 0 and 100")
    strength = float(value)
    if not 0 <= strength <= 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return strength


def apply_anime_cleanup(
    frame: np.ndarray,
    *,
    profile: str,
    denoise: int | float | None = None,
    edge_boost: int | float | None = None,
) -> np.ndarray:
    """Apply profile-guided denoising and edge enhancement to one RGB frame."""
    spec = _PROFILE_SPECS.get(profile)
    if spec is None:
        raise ValueError(f"Unknown Anime cleanup profile: {profile}")
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError("Anime cleanup expects an HWC RGB uint8 frame")

    denoise_strength = _validate_strength(
        "denoise",
        spec["default_denoise"] if denoise is None else denoise,
    )
    edge_strength = _validate_strength(
        "edge_boost",
        spec["default_edge_boost"] if edge_boost is None else edge_boost,
    )
    if denoise_strength == 0 and edge_strength == 0:
        return frame

    image = Image.fromarray(frame)
    if denoise_strength > 0:
        filtered = image.filter(ImageFilter.MedianFilter(size=spec["median_size"]))
        alpha = min(0.9, denoise_strength / 100 * spec["denoise_gain"])
        image = Image.blend(image, filtered, alpha)

    if edge_strength > 0:
        percent = round(min(250, edge_strength * 2 * spec["edge_gain"]))
        image = image.filter(
            ImageFilter.UnsharpMask(
                radius=spec["edge_radius"],
                percent=percent,
                threshold=spec["edge_threshold"],
            )
        )

    return np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
