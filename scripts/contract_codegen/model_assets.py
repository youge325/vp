"""Validate, normalize, and render the neutral model-asset manifest."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def _schema_registry(contracts_dir: Path) -> Registry:
    base_uri = "https://vp-workbench.local/contracts/"
    return Registry().with_resources(
        (
            f"{base_uri}{path.name}",
            Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in contracts_dir.glob("*.schema.json")
    )


def load_model_assets(contracts_dir: Path) -> dict[str, Any]:
    """Load model assets, enforce semantic invariants, and return stable ordering."""

    schema = json.loads((contracts_dir / "model-assets.schema.json").read_text(encoding="utf-8"))
    assets = json.loads((contracts_dir / "model-assets.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=_schema_registry(contracts_dir)).validate(assets)

    normalized = copy.deepcopy(assets)
    families = normalized["families"]
    algorithm_ids = [family["algorithmId"] for family in families]
    implementation_keys = [family["implementationKey"] for family in families]
    if len(algorithm_ids) != len(set(algorithm_ids)):
        raise RuntimeError("model asset algorithm IDs must be unique")
    if len(implementation_keys) != len(set(implementation_keys)):
        raise RuntimeError("model asset implementation keys must be unique")

    all_paths: list[str] = []
    all_file_ids: list[str] = []
    for family in families:
        algorithm = family["algorithmId"]
        context_frames = family["temporalContextFrames"]
        if family["inputFrameMode"] == "fixed_window" and family["defaultNumFrames"] != context_frames * 2 + 1:
            raise RuntimeError(f"{algorithm} fixed window must contain one center frame and symmetric context")
        variants = family["variants"]
        scales = [variant["scaleFactor"] for variant in variants]
        if len(scales) != len(set(scales)):
            raise RuntimeError(f"{algorithm} scale factors must be unique")
        variants.sort(key=lambda variant: variant["scaleFactor"])
        for variant in variants:
            scale = variant["scaleFactor"]
            expected_path = f"models/super_resolution/pytorch/{algorithm}/x{scale}/model.safetensors"
            if variant["relativePath"] != expected_path:
                raise RuntimeError(f"{algorithm} x{scale} runtime path must be {expected_path}")
            all_paths.append(variant["relativePath"])
            all_file_ids.append(variant["googleDriveFileId"])
    if len(all_paths) != len(set(all_paths)):
        raise RuntimeError("model asset runtime paths must be unique")
    if len(all_file_ids) != len(set(all_file_ids)):
        raise RuntimeError("model asset Google Drive file IDs must be unique")
    families.sort(key=lambda family: family["algorithmId"])
    normalized["runtime"]["engines"].sort()
    return normalized


def model_asset_protocol_values(assets: dict[str, Any]) -> dict[str, tuple[object, ...]]:
    """Project strict stage-worker values from the normalized asset inventory."""

    return {
        "algorithmIds": tuple(family["algorithmId"] for family in assets["families"]),
        "scaleFactors": tuple(
            sorted({variant["scaleFactor"] for family in assets["families"] for variant in family["variants"]})
        ),
        "engines": tuple(assets["runtime"]["engines"]),
    }


def _python_string_tuple(values: list[str]) -> str:
    body = ", ".join(json.dumps(value) for value in values)
    return f"({body}{',' if len(values) == 1 else ''})"


def render_python_model_assets(assets: dict[str, Any]) -> str:
    license_info = assets["license"]
    runtime = assets["runtime"]
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
        "class ModelSpatialPolicy:",
        "    minimum_size: int",
        "    size_multiple: int",
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class ModelAssetFamily:",
        "    algorithm_id: str",
        "    display_name: str",
        "    implementation_key: str",
        '    input_frame_mode: Literal["editable_chunk", "fixed_window"]',
        "    default_num_frames: int",
        "    temporal_context_frames: int",
        "    spatial_policy: ModelSpatialPolicy",
        "    runtime_requirements: tuple[str, ...]",
        "    variants: tuple[ModelAssetVariant, ...]",
        "",
        "",
        f"REAL_RAWVSR_ALGORITHM_FAMILY: Final = {json.dumps(runtime['algorithmFamily'])}",
        f"REAL_RAWVSR_TENSOR_BACKEND: Final = {json.dumps(runtime['tensorBackend'])}",
        f"REAL_RAWVSR_ENGINES: Final = {_python_string_tuple(runtime['engines'])}",
        f"REAL_RAWVSR_LICENSE_SPDX: Final = {json.dumps(license_info['spdxId'])}",
        f"REAL_RAWVSR_LICENSE_USAGE: Final = {json.dumps(license_info['usage'])}",
        f"REAL_RAWVSR_SOURCE_URL: Final = {json.dumps(license_info['sourceUrl'])}",
        "REAL_RAWVSR_MODEL_FAMILIES: Final = (",
    ]
    for family in assets["families"]:
        spatial = family["spatialPolicy"]
        requirements = family["runtimeRequirements"]
        lines.extend(
            [
                "    ModelAssetFamily(",
                f"        algorithm_id={json.dumps(family['algorithmId'])},",
                f"        display_name={json.dumps(family['displayName'])},",
                f"        implementation_key={json.dumps(family['implementationKey'])},",
                f"        input_frame_mode={json.dumps(family['inputFrameMode'])},",
                f"        default_num_frames={family['defaultNumFrames']},",
                f"        temporal_context_frames={family['temporalContextFrames']},",
                "        spatial_policy=ModelSpatialPolicy(",
                f"            minimum_size={spatial['minimumSize']},",
                f"            size_multiple={spatial['sizeMultiple']},",
                "        ),",
                f"        runtime_requirements={_python_string_tuple(requirements)},",
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
