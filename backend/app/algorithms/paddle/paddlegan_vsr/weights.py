"""Fixed PaddleGAN VSR weight locations."""

from __future__ import annotations

from pathlib import Path

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS, PaddleGanVsrSpec
from app.config import settings
from app.errors.codes import TaskErrorCode
from app.errors.process import raise_error


def _fixed_weight_root() -> Path:
    """Return the hard-coded repository-local PaddleGAN VSR weight root."""
    return Path(settings.backend_root) / "models" / "super_resolution" / "paddlegan"


def get_spec(model_id: str) -> PaddleGanVsrSpec:
    try:
        return PADDLEGAN_VSR_SPECS[model_id]
    except KeyError:
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Unknown PaddleGAN VSR model: {model_id}",
            details={"model": model_id, "available": sorted(PADDLEGAN_VSR_SPECS)},
        )


def _resolve_weight_path(model_id: str) -> Path:
    spec = get_spec(model_id)
    return _fixed_weight_root() / spec.subdir / spec.filename


def _ensure_weight_file(model_id: str) -> Path:
    """Return a usable repository-local weight path."""
    get_spec(model_id)
    target = _resolve_weight_path(model_id)
    if target.is_file() and target.stat().st_size > 0:
        return target

    raise_error(
        TaskErrorCode.MISSING_MODEL,
        f"PaddleGAN VSR weight is missing: {target}",
        details={"model": model_id, "path": str(target)},
    )


def ensure_paddlegan_vsr_weights(model_id: str) -> Path:
    """Validate all local weights required by a PaddleGAN VSR model."""
    main_weight = _ensure_weight_file(model_id)
    spec = get_spec(model_id)
    auxiliary_root = _fixed_weight_root() / "_auxiliary"
    for filename in spec.auxiliary_filenames:
        target = auxiliary_root / filename
        if target.is_file() and target.stat().st_size > 0:
            continue
        raise_error(
            TaskErrorCode.MISSING_MODEL,
            f"PaddleGAN auxiliary weight is missing: {target}",
            details={"model": model_id, "path": str(target)},
        )
    return main_weight
