"""Integrity-checked access to packaged Real-RawVSR RGB weights."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from app.generated.model_assets import (
    REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM,
    REAL_RAWVSR_MODEL_VARIANTS_BY_KEY,
    ModelAssetFamily,
    ModelAssetVariant,
)


def family_for_algorithm(algorithm_id: str) -> ModelAssetFamily:
    try:
        return REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM[algorithm_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported Real-RawVSR RGB algorithm: {algorithm_id!r}.") from exc


def variant_for_algorithm_scale(algorithm_id: str, scale_factor: int) -> ModelAssetVariant:
    family = family_for_algorithm(algorithm_id)
    try:
        return REAL_RAWVSR_MODEL_VARIANTS_BY_KEY[(algorithm_id, scale_factor)]
    except KeyError as exc:
        raise ValueError(f"{family.display_name} supports only 2x, 3x, and 4x; got {scale_factor}x.") from exc


@lru_cache(maxsize=32)
def _sha256_for_snapshot(path: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_model_asset(model_root: str | Path, algorithm_id: str, scale_factor: int) -> Path:
    family = family_for_algorithm(algorithm_id)
    variant = variant_for_algorithm_scale(algorithm_id, scale_factor)
    model_path = Path(model_root).resolve().parent / Path(variant.relative_path)
    if not model_path.is_file():
        raise FileNotFoundError(f"{family.display_name} x{scale_factor} model weight is missing: {model_path}")
    stat = model_path.stat()
    if stat.st_size != variant.inference_bytes:
        raise RuntimeError(
            f"{family.display_name} x{scale_factor} model weight size mismatch: "
            f"expected {variant.inference_bytes}, got {stat.st_size} ({model_path})."
        )
    actual_sha256 = _sha256_for_snapshot(str(model_path), stat.st_size, stat.st_mtime_ns)
    if actual_sha256 != variant.inference_sha256:
        raise RuntimeError(
            f"{family.display_name} x{scale_factor} model weight SHA-256 mismatch: "
            f"expected {variant.inference_sha256}, got {actual_sha256} ({model_path})."
        )
    return model_path


__all__ = ["ensure_model_asset", "family_for_algorithm", "variant_for_algorithm_scale"]
