"""Shared validation and geometry projection for frame filters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

type FilterParams = Mapping[str, Any]


def _integer(params: FilterParams, name: str, default: int, *, minimum: int) -> int:
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"Filter parameter '{name}' must be a {qualifier} integer.")
    return value


def _scale_factor(params: FilterParams) -> float:
    value = params.get("factor", 1.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Scale filter factor must be a positive finite number.")
    factor = float(value)
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("Scale filter factor must be a positive finite number.")
    return factor


def validate_filter_geometry(kind: str, params: FilterParams) -> None:
    if kind == "scale":
        mode = params.get("mode", "factor")
        if mode == "factor":
            _scale_factor(params)
        elif mode == "resolution":
            _integer(params, "width", 1, minimum=1)
            _integer(params, "height", 1, minimum=1)
        else:
            raise ValueError("Scale filter mode must be 'factor' or 'resolution'.")
    elif kind == "crop":
        _integer(params, "x", 0, minimum=0)
        _integer(params, "y", 0, minimum=0)
        if "width" in params:
            _integer(params, "width", 1, minimum=1)
        if "height" in params:
            _integer(params, "height", 1, minimum=1)
    elif kind == "pad":
        for name in ("top", "bottom", "left", "right"):
            _integer(params, name, 0, minimum=0)


def scale_output_dimensions(
    params: FilterParams,
    *,
    input_width: int,
    input_height: int,
) -> tuple[int, int]:
    validate_filter_geometry("scale", params)
    if params.get("mode", "factor") == "factor":
        factor = _scale_factor(params)
        return max(1, round(input_width * factor)), max(1, round(input_height * factor))
    return (
        _integer(params, "width", input_width, minimum=1),
        _integer(params, "height", input_height, minimum=1),
    )


def crop_slices(
    params: FilterParams,
    *,
    frame_width: int,
    frame_height: int,
) -> tuple[slice, slice]:
    validate_filter_geometry("crop", params)
    x = _integer(params, "x", 0, minimum=0)
    y = _integer(params, "y", 0, minimum=0)
    if x >= frame_width or y >= frame_height:
        raise ValueError("Crop filter origin must lie inside the input frame.")
    width = _integer(params, "width", frame_width, minimum=1)
    height = _integer(params, "height", frame_height, minimum=1)
    return (
        slice(y, min(frame_height, y + height)),
        slice(x, min(frame_width, x + width)),
    )


def padding(params: FilterParams) -> tuple[int, int, int, int]:
    validate_filter_geometry("pad", params)
    return tuple(_integer(params, name, 0, minimum=0) for name in ("top", "bottom", "left", "right"))


def project_filter_chain(
    width: int,
    height: int,
    filters: object,
) -> tuple[int, int]:
    if not isinstance(filters, Sequence) or isinstance(filters, (str, bytes)):
        raise TypeError("Filter chain geometry requires a sequence of filter steps.")
    for raw_filter in filters:
        if not isinstance(raw_filter, Mapping) or raw_filter.get("enabled", True) is False:
            continue
        kind = raw_filter.get("kind")
        raw_params = raw_filter.get("params", {})
        if not isinstance(kind, str) or not isinstance(raw_params, Mapping):
            raise TypeError("Filter chain geometry requires typed filter steps and params.")
        validate_filter_geometry(kind, raw_params)
        if kind == "scale":
            width, height = scale_output_dimensions(raw_params, input_width=width, input_height=height)
        elif kind == "crop":
            rows, columns = crop_slices(raw_params, frame_width=width, frame_height=height)
            width = columns.stop - columns.start
            height = rows.stop - rows.start
        elif kind == "pad":
            top, bottom, left, right = padding(raw_params)
            width += left + right
            height += top + bottom
    return width, height
