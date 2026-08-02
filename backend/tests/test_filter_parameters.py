"""Canonical filter parameter normalization."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.catalog.filter_parameters import normalize_filter_params


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (
            "scale",
            {"mode": "factor", "factor": 0.5, "width": 1920, "height": 1080, "interpolation": "lanczos4"},
        ),
        ("crop", {"x": 0, "y": 0, "width": 1920, "height": 1080}),
        ("pad", {"top": 0, "bottom": 0, "left": 0, "right": 0, "color": "#000000"}),
        ("sharpen", {"amount": 0.5}),
        ("denoise", {"strength": 10.0, "colorStrength": 10.0}),
        ("color", {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0}),
        ("anime_cleanup", {"profile": "clean-lines", "denoise": 15.0, "edgeBoost": 30.0}),
    ],
)
def test_filter_defaults_are_normalized_once_into_an_immutable_mapping(
    kind: str,
    expected: dict[str, object],
) -> None:
    params = normalize_filter_params(kind, {})

    assert isinstance(params, MappingProxyType)
    assert params == expected
    with pytest.raises(TypeError):
        params["unexpected"] = True  # type: ignore[index]


def test_anime_profile_defaults_are_selected_before_explicit_overrides() -> None:
    params = normalize_filter_params("anime_cleanup", {"profile": "thin-outline", "denoise": 0})

    assert params == {"profile": "thin-outline", "denoise": 0.0, "edgeBoost": 45.0}


@pytest.mark.parametrize(
    ("kind", "params"),
    [
        ("scale", {"factor": 0}),
        ("pad", {"top": -1}),
        ("color", {"contrast": 4}),
        ("anime_cleanup", {"profile": "missing"}),
        ("sharpen", {"legacyAmount": 1}),
    ],
)
def test_filter_normalization_rejects_schema_mismatches(kind: str, params: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        normalize_filter_params(kind, params)


def test_filter_normalization_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown filter kind"):
        normalize_filter_params("legacy", {})
