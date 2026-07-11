"""Fixed PaddleGAN VSR weight locations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.errors import TaskErrorCode, raise_error


@dataclass(frozen=True, slots=True)
class _PaddleGanVsrSpec:
    """Metadata for one bundled PaddleGAN video super-resolution model."""

    model_id: str
    subdir: str
    filename: str
    sequence_mode: str
    default_num_frames: int
    auxiliary_filenames: tuple[str, ...] = ()


PADDLEGAN_VSR_SPECS: dict[str, _PaddleGanVsrSpec] = {
    "ppmsvsr": _PaddleGanVsrSpec(
        model_id="ppmsvsr",
        subdir="ppmsvsr",
        filename="PP-MSVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("modified_spynet_tiny.pdparams",),
    ),
    "ppmsvsr-large": _PaddleGanVsrSpec(
        model_id="ppmsvsr-large",
        subdir="ppmsvsr-large",
        filename="PP-MSVSR-L_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("modified_spynet.pdparams",),
    ),
    "edvr": _PaddleGanVsrSpec(
        model_id="edvr",
        subdir="edvr",
        filename="EDVR_L_w_tsa_SRx4.pdparams",
        sequence_mode="window",
        default_num_frames=5,
    ),
    "basicvsr": _PaddleGanVsrSpec(
        model_id="basicvsr",
        subdir="basicvsr",
        filename="BasicVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams",),
    ),
    "iconvsr": _PaddleGanVsrSpec(
        model_id="iconvsr",
        subdir="iconvsr",
        filename="IconVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams", "edvrm.pdparams"),
    ),
    "basicvsr-plus-plus": _PaddleGanVsrSpec(
        model_id="basicvsr-plus-plus",
        subdir="basicvsr-plus-plus",
        filename="BasicVSR++_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams",),
    ),
}


def fixed_weight_root() -> Path:
    """Return the hard-coded repository-local PaddleGAN VSR weight root."""
    return Path(settings.backend_root) / "models" / "super_resolution" / "paddlegan"


def get_spec(model_id: str) -> _PaddleGanVsrSpec:
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
    return fixed_weight_root() / spec.subdir / spec.filename


def _ensure_weight_file(
    model_id: str,
    *,
    auto_download: bool | None = None,
) -> Path:
    """Return a usable local weight path.

    ``auto_download`` is accepted for backward-compatible configs but is ignored.
    All PaddleGAN VSR weights must be pre-provisioned under ``fixed_weight_root``.
    """
    get_spec(model_id)
    target = _resolve_weight_path(model_id)
    if target.is_file() and target.stat().st_size > 0:
        return target

    raise_error(
        TaskErrorCode.MISSING_MODEL,
        f"PaddleGAN VSR weight is missing: {target}",
        details={"model": model_id, "path": str(target)},
    )


def ensure_paddlegan_vsr_weights(
    model_id: str,
    *,
    auto_download: bool | None = None,
) -> Path:
    """Validate all local weights required by a PaddleGAN VSR model."""
    main_weight = _ensure_weight_file(model_id, auto_download=auto_download)
    spec = get_spec(model_id)
    auxiliary_root = fixed_weight_root() / "_auxiliary"
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
