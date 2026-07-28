"""Neutral metadata for bundled PaddleGAN video super-resolution models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaddleGanVsrSpec:
    model_id: str
    subdir: str
    filename: str
    sequence_mode: str
    default_num_frames: int
    auxiliary_filenames: tuple[str, ...] = ()


PADDLEGAN_VSR_SPECS: dict[str, PaddleGanVsrSpec] = {
    "ppmsvsr": PaddleGanVsrSpec(
        model_id="ppmsvsr",
        subdir="ppmsvsr",
        filename="PP-MSVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("modified_spynet_tiny.pdparams",),
    ),
    "ppmsvsr-large": PaddleGanVsrSpec(
        model_id="ppmsvsr-large",
        subdir="ppmsvsr-large",
        filename="PP-MSVSR-L_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("modified_spynet.pdparams",),
    ),
    "edvr": PaddleGanVsrSpec(
        model_id="edvr",
        subdir="edvr",
        filename="EDVR_L_w_tsa_SRx4.pdparams",
        sequence_mode="window",
        default_num_frames=5,
    ),
    "basicvsr": PaddleGanVsrSpec(
        model_id="basicvsr",
        subdir="basicvsr",
        filename="BasicVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams",),
    ),
    "iconvsr": PaddleGanVsrSpec(
        model_id="iconvsr",
        subdir="iconvsr",
        filename="IconVSR_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams", "edvrm.pdparams"),
    ),
    "basicvsr-plus-plus": PaddleGanVsrSpec(
        model_id="basicvsr-plus-plus",
        subdir="basicvsr-plus-plus",
        filename="BasicVSR++_reds_x4.pdparams",
        sequence_mode="recurrent",
        default_num_frames=10,
        auxiliary_filenames=("spynet.pdparams",),
    ),
}


__all__ = ["PADDLEGAN_VSR_SPECS", "PaddleGanVsrSpec"]
