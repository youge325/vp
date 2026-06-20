"""Fixed PaddleGAN VSR weight locations and download helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import urlretrieve

from app.config import settings
from app.errors import TaskErrorCode, raise_error


@dataclass(frozen=True, slots=True)
class PaddleGanVsrSpec:
    """Metadata for one bundled PaddleGAN video super-resolution model."""

    model_id: str
    display_name: str
    subdir: str
    filename: str
    url: str
    sequence_mode: str
    default_num_frames: int


PADDLEGAN_VSR_SPECS: dict[str, PaddleGanVsrSpec] = {
    "ppmsvsr": PaddleGanVsrSpec(
        model_id="ppmsvsr",
        display_name="PP-MSVSR",
        subdir="ppmsvsr",
        filename="PP-MSVSR_reds_x4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/PP-MSVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
    ),
    "ppmsvsr-large": PaddleGanVsrSpec(
        model_id="ppmsvsr-large",
        display_name="PP-MSVSR-L",
        subdir="ppmsvsr-large",
        filename="PP-MSVSR-L_reds_x4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/PP-MSVSR-L_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
    ),
    "edvr": PaddleGanVsrSpec(
        model_id="edvr",
        display_name="EDVR",
        subdir="edvr",
        filename="EDVR_L_w_tsa_SRx4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/EDVR_L_w_tsa_SRx4.pdparams",
        sequence_mode="window",
        default_num_frames=5,
    ),
    "basicvsr": PaddleGanVsrSpec(
        model_id="basicvsr",
        display_name="BasicVSR",
        subdir="basicvsr",
        filename="BasicVSR_reds_x4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/BasicVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
    ),
    "iconvsr": PaddleGanVsrSpec(
        model_id="iconvsr",
        display_name="IconVSR",
        subdir="iconvsr",
        filename="IconVSR_reds_x4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/IconVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
    ),
    "basicvsr-plus-plus": PaddleGanVsrSpec(
        model_id="basicvsr-plus-plus",
        display_name="BasicVSR++",
        subdir="basicvsr-plus-plus",
        filename="BasicVSR++_reds_x4.pdparams",
        url="https://paddlegan.bj.bcebos.com/models/BasicVSR%2B%2B_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
    ),
}

Downloader = Callable[[str, Path], None]


def fixed_weight_root() -> Path:
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


def resolve_weight_path(model_id: str) -> Path:
    spec = get_spec(model_id)
    return fixed_weight_root() / spec.subdir / spec.filename


def _default_downloader(url: str, destination: Path) -> None:
    urlretrieve(url, destination)


def ensure_weight_file(
    model_id: str,
    *,
    auto_download: bool,
    downloader: Downloader | None = None,
) -> Path:
    """Return a usable weight path, downloading into the fixed cache when allowed."""
    spec = get_spec(model_id)
    target = resolve_weight_path(model_id)
    if target.is_file() and target.stat().st_size > 0:
        return target

    if not auto_download:
        raise_error(
            TaskErrorCode.MISSING_MODEL,
            f"PaddleGAN VSR weight is missing: {target}",
            details={"model": model_id, "path": str(target), "url": spec.url},
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(f"{target.suffix}.tmp")
    tmp_path.unlink(missing_ok=True)
    download = downloader or _default_downloader
    try:
        download(spec.url, tmp_path)
        if not tmp_path.is_file() or tmp_path.stat().st_size <= 0:
            raise RuntimeError(f"Downloaded file is empty: {tmp_path}")
        tmp_path.replace(target)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise_error(
            TaskErrorCode.MISSING_MODEL,
            f"Failed to download PaddleGAN VSR weight for {model_id}: {exc}",
            details={"model": model_id, "url": spec.url, "path": str(target)},
        )
    return target
