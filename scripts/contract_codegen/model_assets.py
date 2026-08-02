"""Validate and render the neutral model-asset manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_ALGORITHM_ORDER = (
    "real-rawvsr-basicvsr",
    "real-rawvsr-edvr",
    "real-rawvsr-tdan",
    "real-rawvsr-toflow",
)


def load_model_assets(contracts_dir: Path) -> dict[str, Any]:
    """Load model assets and enforce cross-field invariants not expressible in JSON Schema."""

    schema = json.loads((contracts_dir / "model-assets.schema.json").read_text(encoding="utf-8"))
    assets = json.loads((contracts_dir / "model-assets.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(assets)

    families = assets["families"]
    algorithms = tuple(family["algorithmId"] for family in families)
    if algorithms != _ALGORITHM_ORDER:
        raise RuntimeError(f"Real-RawVSR model families must be ordered exactly as {_ALGORITHM_ORDER!r}")

    all_paths: list[str] = []
    all_file_ids: list[str] = []
    for family in families:
        algorithm = family["algorithmId"]
        variants = family["variants"]
        if [variant["scaleFactor"] for variant in variants] != [2, 3, 4]:
            raise RuntimeError(f"{algorithm} variants must be ordered exactly as scales 2, 3, and 4")
        expected_mode = "editable_chunk" if algorithm == "real-rawvsr-basicvsr" else "fixed_window"
        expected_frames = 10 if algorithm == "real-rawvsr-basicvsr" else 5
        if family["inputFrameMode"] != expected_mode or family["defaultNumFrames"] != expected_frames:
            raise RuntimeError(f"{algorithm} temporal policy does not match its supported inference mode")
        for variant in variants:
            expected_fragment = f"/{algorithm}/x{variant['scaleFactor']}/"
            if expected_fragment not in f"/{variant['relativePath']}":
                raise RuntimeError("model asset algorithm and scale factor must match its runtime path")
            all_paths.append(variant["relativePath"])
            all_file_ids.append(variant["googleDriveFileId"])
    if len(all_paths) != len(set(all_paths)):
        raise RuntimeError("model asset runtime paths must be unique")
    if len(all_file_ids) != len(set(all_file_ids)):
        raise RuntimeError("model asset Google Drive file IDs must be unique")
    return assets


def render_python_model_assets(assets: dict[str, Any]) -> str:
    license_info = assets["license"]
    lines = [
        '"""Generated from contracts/model-assets.json. Do not edit."""',
        "",
        "from dataclasses import dataclass",
        "from types import MappingProxyType",
        "from typing import Final, Literal",
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class ModelAssetVariant:",
        "    scale_factor: int",
        "    inference_bytes: int",
        "    inference_sha256: str",
        "    parameter_count: int",
        "    relative_path: str",
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class ModelAssetFamily:",
        "    algorithm_id: str",
        "    display_name: str",
        '    input_frame_mode: Literal["editable_chunk", "fixed_window"]',
        "    default_num_frames: int",
        "    temporal_context_frames: int",
        "    variants: tuple[ModelAssetVariant, ...]",
        "",
        "",
        f"REAL_RAWVSR_LICENSE_SPDX: Final = {json.dumps(license_info['spdxId'])}",
        f"REAL_RAWVSR_LICENSE_USAGE: Final = {json.dumps(license_info['usage'])}",
        f"REAL_RAWVSR_SOURCE_URL: Final = {json.dumps(license_info['sourceUrl'])}",
        "REAL_RAWVSR_MODEL_FAMILIES: Final = (",
    ]
    for family in assets["families"]:
        lines.extend(
            [
                "    ModelAssetFamily(",
                f"        algorithm_id={json.dumps(family['algorithmId'])},",
                f"        display_name={json.dumps(family['displayName'])},",
                f"        input_frame_mode={json.dumps(family['inputFrameMode'])},",
                f"        default_num_frames={family['defaultNumFrames']},",
                f"        temporal_context_frames={family['temporalContextFrames']},",
                "        variants=(",
            ]
        )
        for variant in family["variants"]:
            lines.extend(
                [
                    "            ModelAssetVariant(",
                    f"                scale_factor={variant['scaleFactor']},",
                    f"                inference_bytes={variant['inferenceBytes']},",
                    f"                inference_sha256={json.dumps(variant['inferenceSha256'])},",
                    f"                parameter_count={variant['parameterCount']},",
                    f"                relative_path={json.dumps(variant['relativePath'])},",
                    "            ),",
                ]
            )
        lines.extend(["        ),", "    ),"])
    lines.extend(
        [
            ")",
            "REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM: Final = MappingProxyType(",
            "    {family.algorithm_id: family for family in REAL_RAWVSR_MODEL_FAMILIES}",
            ")",
            "REAL_RAWVSR_MODEL_VARIANTS_BY_KEY: Final = MappingProxyType(",
            "    {",
            "        (family.algorithm_id, variant.scale_factor): variant",
            "        for family in REAL_RAWVSR_MODEL_FAMILIES",
            "        for variant in family.variants",
            "    }",
            ")",
            "",
        ]
    )
    return "\n".join(lines)


def render_rust_model_assets(assets: dict[str, Any]) -> str:
    license_info = assets["license"]
    lines = [
        "// Generated from contracts/model-assets.json. Do not edit.",
        "#[derive(Clone, Copy)]",
        "pub(crate) struct ModelAssetVariant {",
        "    pub(crate) scale_factor: u32,",
        "    pub(crate) inference_bytes: u64,",
        "    pub(crate) inference_sha256: &'static str,",
        "    pub(crate) relative_path: &'static str,",
        "}",
        "",
        "pub(crate) struct ModelAssetFamily {",
        "    pub(crate) algorithm_id: &'static str,",
        "    pub(crate) display_name: &'static str,",
        "    pub(crate) variants: &'static [ModelAssetVariant],",
        "}",
        "",
        f"pub(crate) const REAL_RAWVSR_LICENSE_PATH: &str = {json.dumps(license_info['licenseRelativePath'])};",
        f"pub(crate) const REAL_RAWVSR_NOTICE_PATH: &str = {json.dumps(license_info['noticeRelativePath'])};",
        "pub(crate) const REAL_RAWVSR_THIRD_PARTY_NOTICE_PATH: &str =",
        f"    {json.dumps(license_info['thirdPartyNoticeRelativePath'])};",
        "",
    ]
    variant_names: list[tuple[str, str, str]] = []
    for index, family in enumerate(assets["families"]):
        variant_name = f"REAL_RAWVSR_FAMILY_{index}_VARIANTS"
        variant_names.append((variant_name, family["algorithmId"], family["displayName"]))
        lines.append(f"const {variant_name}: &[ModelAssetVariant] = &[")
        for variant in family["variants"]:
            lines.extend(
                [
                    "    ModelAssetVariant {",
                    f"        scale_factor: {variant['scaleFactor']},",
                    f"        inference_bytes: {variant['inferenceBytes']},",
                    f"        inference_sha256: {json.dumps(variant['inferenceSha256'])},",
                    f"        relative_path: {json.dumps(variant['relativePath'])},",
                    "    },",
                ]
            )
        lines.extend(["];", ""])
    lines.append("pub(crate) const REAL_RAWVSR_MODEL_FAMILIES: &[ModelAssetFamily] = &[")
    for variant_name, algorithm_id, display_name in variant_names:
        lines.extend(
            [
                "    ModelAssetFamily {",
                f"        algorithm_id: {json.dumps(algorithm_id)},",
                f"        display_name: {json.dumps(display_name)},",
                f"        variants: {variant_name},",
                "    },",
            ]
        )
    lines.extend(["];", ""])
    return "\n".join(lines)
