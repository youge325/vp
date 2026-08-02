"""Generated from contracts/model-assets.json. Do not edit."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelAssetVariant:
    scale_factor: int
    inference_bytes: int
    inference_sha256: str
    relative_path: str


REAL_RAWVSR_BASICVSR_ALGORITHM: Final = "real-rawvsr-basicvsr"
REAL_RAWVSR_BASICVSR_DEFAULT_NUM_FRAMES: Final = 10
REAL_RAWVSR_BASICVSR_CONTEXT_FRAMES: Final = 2
REAL_RAWVSR_BASICVSR_LICENSE_SPDX: Final = "CC-BY-NC-SA-4.0"
REAL_RAWVSR_BASICVSR_LICENSE_USAGE: Final = "non_commercial"
REAL_RAWVSR_BASICVSR_SOURCE_URL: Final = "https://github.com/zmzhang1998/Real-RawVSR"
REAL_RAWVSR_BASICVSR_VARIANTS: Final = (
    ModelAssetVariant(
        scale_factor=2,
        inference_bytes=24608772,
        inference_sha256="19e06889ff7e96f3904c24562667949bb7e452ab02234508db51759741c91efb",
        relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x2/model.safetensors",
    ),
    ModelAssetVariant(
        scale_factor=3,
        inference_bytes=25347332,
        inference_sha256="01dbec2b5827f868d89a12abe9aadb9952f6bc05b28c233f10884cfc18a59914",
        relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x3/model.safetensors",
    ),
    ModelAssetVariant(
        scale_factor=4,
        inference_bytes=25199820,
        inference_sha256="bc8e5f0d545d049a8268d9a980062aa83ee86ce0c998e104a245d5190dab2295",
        relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x4/model.safetensors",
    ),
)
REAL_RAWVSR_BASICVSR_VARIANTS_BY_SCALE: Final = MappingProxyType(
    {variant.scale_factor: variant for variant in REAL_RAWVSR_BASICVSR_VARIANTS}
)
