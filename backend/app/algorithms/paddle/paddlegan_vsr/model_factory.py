"""Lazy, exact-set PaddleGAN model factories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS

ModelFactory = Callable[[], Any]


def _edvr() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.edvr import EDVRNet

    return EDVRNet(nf=128, back_RBs=40)


def _basicvsr() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.basicvsr import BasicVSRNet

    return BasicVSRNet()


def _iconvsr() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.iconvsr import IconVSR

    return IconVSR()


def _basicvsr_plus_plus() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.basicvsr_plus_plus import (
        BasicVSRPlusPlus,
    )

    return BasicVSRPlusPlus()


def _ppmsvsr() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.msvsr import MSVSR

    return MSVSR()


def _ppmsvsr_large() -> Any:
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.models.generators.msvsr import MSVSR

    return MSVSR(
        mid_channels=64,
        num_init_blocks=5,
        num_blocks=7,
        num_reconstruction_blocks=5,
        only_last=False,
        use_tiny_spynet=False,
        deform_groups=8,
        aux_reconstruction_blocks=2,
    )


_MODEL_FACTORIES: dict[str, ModelFactory] = {
    "ppmsvsr": _ppmsvsr,
    "ppmsvsr-large": _ppmsvsr_large,
    "edvr": _edvr,
    "basicvsr": _basicvsr,
    "iconvsr": _iconvsr,
    "basicvsr-plus-plus": _basicvsr_plus_plus,
}


def _validate_model_factory_registry() -> None:
    missing = sorted(set(PADDLEGAN_VSR_SPECS) - set(_MODEL_FACTORIES))
    extra = sorted(set(_MODEL_FACTORIES) - set(PADDLEGAN_VSR_SPECS))
    if missing or extra:
        raise RuntimeError(f"PaddleGAN model factory registry drift: missing={missing}, extra={extra}")


def build_paddlegan_model(model_id: str) -> Any:
    try:
        factory = _MODEL_FACTORIES[model_id]
    except KeyError as exc:
        raise ValueError(f"No PaddleGAN model factory is registered for {model_id!r}") from exc
    return factory()


_validate_model_factory_registry()

__all__ = ["build_paddlegan_model"]
