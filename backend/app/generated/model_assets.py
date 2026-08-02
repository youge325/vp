"""Generated from contracts/model-assets.json. Do not edit."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal


@dataclass(frozen=True, slots=True)
class ModelAssetVariant:
    scale_factor: int
    inference_bytes: int
    inference_sha256: str
    parameter_count: int
    relative_path: str


@dataclass(frozen=True, slots=True)
class ModelAssetFamily:
    algorithm_id: str
    display_name: str
    input_frame_mode: Literal["editable_chunk", "fixed_window"]
    default_num_frames: int
    temporal_context_frames: int
    variants: tuple[ModelAssetVariant, ...]


REAL_RAWVSR_LICENSE_SPDX: Final = "CC-BY-NC-SA-4.0"
REAL_RAWVSR_LICENSE_USAGE: Final = "non_commercial"
REAL_RAWVSR_SOURCE_URL: Final = "https://github.com/zmzhang1998/Real-RawVSR"
REAL_RAWVSR_MODEL_FAMILIES: Final = (
    ModelAssetFamily(
        algorithm_id="real-rawvsr-basicvsr",
        display_name="Real-RawVSR BasicVSR",
        input_frame_mode="editable_chunk",
        default_num_frames=10,
        temporal_context_frames=2,
        variants=(
            ModelAssetVariant(
                scale_factor=2,
                inference_bytes=24608772,
                inference_sha256="19e06889ff7e96f3904c24562667949bb7e452ab02234508db51759741c91efb",
                parameter_count=6143599,
                relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x2/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=3,
                inference_bytes=25347332,
                inference_sha256="01dbec2b5827f868d89a12abe9aadb9952f6bc05b28c233f10884cfc18a59914",
                parameter_count=6328239,
                relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x3/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=4,
                inference_bytes=25199820,
                inference_sha256="bc8e5f0d545d049a8268d9a980062aa83ee86ce0c998e104a245d5190dab2295",
                parameter_count=6291311,
                relative_path="models/super_resolution/pytorch/real-rawvsr-basicvsr/x4/model.safetensors",
            ),
        ),
    ),
    ModelAssetFamily(
        algorithm_id="real-rawvsr-edvr",
        display_name="Real-RawVSR EDVR",
        input_frame_mode="fixed_window",
        default_num_frames=5,
        temporal_context_frames=2,
        variants=(
            ModelAssetVariant(
                scale_factor=2,
                inference_bytes=12623308,
                inference_sha256="f237abefeff26bef1077fcab1ee096b7056858ac16c05cd8a1bf0f7a8a73c02e",
                parameter_count=3152419,
                relative_path="models/super_resolution/pytorch/real-rawvsr-edvr/x2/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=3,
                inference_bytes=13361868,
                inference_sha256="2138f338398f236b91b56385318ef24e316eab1df7e415c6841c50680400dc15",
                parameter_count=3337059,
                relative_path="models/super_resolution/pytorch/real-rawvsr-edvr/x3/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=4,
                inference_bytes=13214324,
                inference_sha256="cf947c5a93d8616fe879272eab456d740a1666a4c6310a7af9aa152e30676c34",
                parameter_count=3300131,
                relative_path="models/super_resolution/pytorch/real-rawvsr-edvr/x4/model.safetensors",
            ),
        ),
    ),
    ModelAssetFamily(
        algorithm_id="real-rawvsr-tdan",
        display_name="Real-RawVSR TDAN",
        input_frame_mode="fixed_window",
        default_num_frames=5,
        temporal_context_frames=2,
        variants=(
            ModelAssetVariant(
                scale_factor=2,
                inference_bytes=8557668,
                inference_sha256="8d729c685899a88d02c60b37c38eab5af0c6b2b119602a72a3bade36d9ae8c51",
                parameter_count=2137251,
                relative_path="models/super_resolution/pytorch/real-rawvsr-tdan/x2/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=3,
                inference_bytes=9296228,
                inference_sha256="e5167c65adb60c45e491d090af8c4340f700ca653728aa6abe87deaa2772df29",
                parameter_count=2321891,
                relative_path="models/super_resolution/pytorch/real-rawvsr-tdan/x3/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=4,
                inference_bytes=9148676,
                inference_sha256="5098c026063c09de5ed064409f2a9741b058fa0e4b7a62aa929d4796ae6b67da",
                parameter_count=2284963,
                relative_path="models/super_resolution/pytorch/real-rawvsr-tdan/x4/model.safetensors",
            ),
        ),
    ),
    ModelAssetFamily(
        algorithm_id="real-rawvsr-toflow",
        display_name="Real-RawVSR TOFlow",
        input_frame_mode="fixed_window",
        default_num_frames=5,
        temporal_context_frames=2,
        variants=(
            ModelAssetVariant(
                scale_factor=2,
                inference_bytes=5516628,
                inference_sha256="38ddb333e3c0befae3ab7bf3821bfc856fc81ec9dd980f66afc621b9ce5c783f",
                parameter_count=1375969,
                relative_path="models/super_resolution/pytorch/real-rawvsr-toflow/x2/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=3,
                inference_bytes=5516628,
                inference_sha256="c1357bc9c16416eda2f7ded3eb8ef6c13068a219dab5a922b428e6593c1fd701",
                parameter_count=1375969,
                relative_path="models/super_resolution/pytorch/real-rawvsr-toflow/x3/model.safetensors",
            ),
            ModelAssetVariant(
                scale_factor=4,
                inference_bytes=5516628,
                inference_sha256="15efc76c7821d55c6d8882b4d4fbe4695d4dbff9f56b45730cec671de0907b77",
                parameter_count=1375969,
                relative_path="models/super_resolution/pytorch/real-rawvsr-toflow/x4/model.safetensors",
            ),
        ),
    ),
)
REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM: Final = MappingProxyType(
    {family.algorithm_id: family for family in REAL_RAWVSR_MODEL_FAMILIES}
)
REAL_RAWVSR_MODEL_VARIANTS_BY_KEY: Final = MappingProxyType(
    {
        (family.algorithm_id, variant.scale_factor): variant
        for family in REAL_RAWVSR_MODEL_FAMILIES
        for variant in family.variants
    }
)
