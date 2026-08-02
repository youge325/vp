"""Shared validation and geometry projection for frame filters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from app.catalog.filter_parameters import FilterParams, normalize_filter_params


def scale_output_dimensions(
    params: FilterParams,
    *,
    input_width: int,
    input_height: int,
) -> tuple[int, int]:
    if params["mode"] == "factor":
        factor = float(params["factor"])
        return max(1, round(input_width * factor)), max(1, round(input_height * factor))
    return int(params["width"]), int(params["height"])


def crop_slices(
    params: FilterParams,
    *,
    frame_width: int,
    frame_height: int,
) -> tuple[slice, slice]:
    x = int(params["x"])
    y = int(params["y"])
    if x >= frame_width or y >= frame_height:
        raise ValueError("Crop filter origin must lie inside the input frame.")
    width = int(params["width"])
    height = int(params["height"])
    return (
        slice(y, min(frame_height, y + height)),
        slice(x, min(frame_width, x + width)),
    )


def padding(params: FilterParams) -> tuple[int, int, int, int]:
    return tuple(int(params[name]) for name in ("top", "bottom", "left", "right"))


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
        params = normalize_filter_params(kind, raw_params)
        if kind == "scale":
            width, height = scale_output_dimensions(params, input_width=width, input_height=height)
        elif kind == "crop":
            rows, columns = crop_slices(params, frame_width=width, frame_height=height)
            width = columns.stop - columns.start
            height = rows.stop - rows.start
        elif kind == "pad":
            top, bottom, left, right = padding(params)
            width += left + right
            height += top + bottom
    return width, height
