"""Canonical filter defaults, schema validation, and immutable normalization."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from pydantic import BaseModel

from app.generated.application_defaults import FILTER_DEFAULTS
from app.generated.contracts import (
    AnimeCleanupFilterParams,
    ColorFilterParams,
    CropFilterParams,
    DenoiseFilterParams,
    PadFilterParams,
    ScaleFilterParams,
    SharpenFilterParams,
)

type FilterParams = Mapping[str, Any]

_PARAM_MODELS: Final[Mapping[str, type[BaseModel]]] = MappingProxyType(
    {
        "scale": ScaleFilterParams,
        "crop": CropFilterParams,
        "pad": PadFilterParams,
        "sharpen": SharpenFilterParams,
        "denoise": DenoiseFilterParams,
        "color": ColorFilterParams,
        "anime_cleanup": AnimeCleanupFilterParams,
    }
)


def _defaults_for(kind: str, params: FilterParams) -> dict[str, Any]:
    if kind != "anime_cleanup":
        defaults = FILTER_DEFAULTS.get(kind)
        if not isinstance(defaults, Mapping):
            raise ValueError(f"Unknown filter kind: {kind}")
        return {**defaults, **params}

    anime_defaults = FILTER_DEFAULTS["animeCleanup"]
    profile = params.get("profile", anime_defaults["defaultProfile"])
    profile_defaults = anime_defaults["profiles"].get(profile)
    if not isinstance(profile_defaults, Mapping):
        raise ValueError(f"Unknown Anime cleanup profile: {profile}")
    return {"profile": profile, **profile_defaults, **params}


def normalize_filter_params(kind: str, params: FilterParams) -> FilterParams:
    """Merge one partial filter payload with product defaults and validate it once."""

    model = _PARAM_MODELS.get(kind)
    if model is None:
        raise ValueError(f"Unknown filter kind: {kind}")
    normalized = model.model_validate(_defaults_for(kind, params)).model_dump(
        by_alias=True,
        exclude_none=True,
        mode="json",
    )
    return MappingProxyType(normalized)


__all__ = ["FilterParams", "normalize_filter_params"]
