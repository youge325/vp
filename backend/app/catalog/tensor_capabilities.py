"""Immutable tensor runtime engine capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

BACKEND_ENGINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pytorch": ("cuda", "tensorrt"),
        "paddle": ("cuda", "tensorrt", "dcu"),
        "onnx": ("tensorrt", "cuda"),
    }
)


def supports_backend_engine(backend: str, engine: str) -> bool:
    return engine in BACKEND_ENGINES.get(backend, ())


__all__ = ["BACKEND_ENGINES", "supports_backend_engine"]
