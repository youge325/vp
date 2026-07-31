"""Neutral metadata for bundled PaddleGAN video super-resolution models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

PaddleGanSequenceMode = Literal["recurrent", "window"]


@dataclass(frozen=True, slots=True)
class PaddleGanVsrSpec:
    subdir: str
    filename: str
    sequence_mode: PaddleGanSequenceMode
    default_num_frames: int
    auxiliary_filenames: tuple[str, ...] = ()


PADDLEGAN_VSR_SPECS: Mapping[str, PaddleGanVsrSpec] = MappingProxyType(
    {
        "ppmsvsr": PaddleGanVsrSpec(
            subdir="ppmsvsr",
            filename="PP-MSVSR_reds_x4.pdparams",
            sequence_mode="recurrent",
            default_num_frames=10,
            auxiliary_filenames=("modified_spynet_tiny.pdparams",),
        ),
        "ppmsvsr-large": PaddleGanVsrSpec(
            subdir="ppmsvsr-large",
            filename="PP-MSVSR-L_reds_x4.pdparams",
            sequence_mode="recurrent",
            default_num_frames=10,
            auxiliary_filenames=("modified_spynet.pdparams",),
        ),
        "edvr": PaddleGanVsrSpec(
            subdir="edvr",
            filename="EDVR_L_w_tsa_SRx4.pdparams",
            sequence_mode="window",
            default_num_frames=5,
        ),
        "basicvsr": PaddleGanVsrSpec(
            subdir="basicvsr",
            filename="BasicVSR_reds_x4.pdparams",
            sequence_mode="recurrent",
            default_num_frames=10,
            auxiliary_filenames=("spynet.pdparams",),
        ),
        "iconvsr": PaddleGanVsrSpec(
            subdir="iconvsr",
            filename="IconVSR_reds_x4.pdparams",
            sequence_mode="recurrent",
            default_num_frames=10,
            auxiliary_filenames=("spynet.pdparams", "edvrm.pdparams"),
        ),
        "basicvsr-plus-plus": PaddleGanVsrSpec(
            subdir="basicvsr-plus-plus",
            filename="BasicVSR++_reds_x4.pdparams",
            sequence_mode="recurrent",
            default_num_frames=10,
            auxiliary_filenames=("spynet.pdparams",),
        ),
    }
)


__all__ = ["PADDLEGAN_VSR_SPECS", "PaddleGanSequenceMode", "PaddleGanVsrSpec"]
