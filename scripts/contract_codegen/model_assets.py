"""Validate and render the neutral model-asset manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_model_assets(contracts_dir: Path) -> dict[str, Any]:
    """Load model assets and enforce cross-field invariants not expressible in JSON Schema."""

    schema = json.loads((contracts_dir / "model-assets.schema.json").read_text(encoding="utf-8"))
    assets = json.loads((contracts_dir / "model-assets.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(assets)

    family = assets["realRawVsrBasicVsr"]
    variants = family["variants"]
    scales = [variant["scaleFactor"] for variant in variants]
    if scales != [2, 3, 4]:
        raise RuntimeError("Real-RawVSR BasicVSR variants must be ordered exactly as scales 2, 3, and 4")
    paths = [variant["relativePath"] for variant in variants]
    if len(paths) != len(set(paths)):
        raise RuntimeError("model asset runtime paths must be unique")
    for variant in variants:
        expected_fragment = f"/x{variant['scaleFactor']}/"
        if expected_fragment not in f"/{variant['relativePath']}":
            raise RuntimeError("model asset scale factor must match its runtime path")
    return assets


def render_python_model_assets(assets: dict[str, Any]) -> str:
    family = assets["realRawVsrBasicVsr"]
    license_info = family["license"]
    lines = [
        '"""Generated from contracts/model-assets.json. Do not edit."""',
        "",
        "from dataclasses import dataclass",
        "from types import MappingProxyType",
        "from typing import Final",
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class ModelAssetVariant:",
        "    scale_factor: int",
        "    inference_bytes: int",
        "    inference_sha256: str",
        "    relative_path: str",
        "",
        "",
        f"REAL_RAWVSR_BASICVSR_ALGORITHM: Final = {json.dumps(family['algorithmId'])}",
        f"REAL_RAWVSR_BASICVSR_DEFAULT_NUM_FRAMES: Final = {family['defaultNumFrames']}",
        f"REAL_RAWVSR_BASICVSR_CONTEXT_FRAMES: Final = {family['temporalContextFrames']}",
        f"REAL_RAWVSR_BASICVSR_LICENSE_SPDX: Final = {json.dumps(license_info['spdxId'])}",
        f"REAL_RAWVSR_BASICVSR_LICENSE_USAGE: Final = {json.dumps(license_info['usage'])}",
        f"REAL_RAWVSR_BASICVSR_SOURCE_URL: Final = {json.dumps(license_info['sourceUrl'])}",
        "REAL_RAWVSR_BASICVSR_VARIANTS: Final = (",
    ]
    for variant in family["variants"]:
        lines.extend(
            [
                "    ModelAssetVariant(",
                f"        scale_factor={variant['scaleFactor']},",
                f"        inference_bytes={variant['inferenceBytes']},",
                f"        inference_sha256={json.dumps(variant['inferenceSha256'])},",
                f"        relative_path={json.dumps(variant['relativePath'])},",
                "    ),",
            ]
        )
    lines.extend(
        [
            ")",
            "REAL_RAWVSR_BASICVSR_VARIANTS_BY_SCALE: Final = MappingProxyType(",
            "    {variant.scale_factor: variant for variant in REAL_RAWVSR_BASICVSR_VARIANTS}",
            ")",
            "",
        ]
    )
    return "\n".join(lines)


def render_rust_model_assets(assets: dict[str, Any]) -> str:
    family = assets["realRawVsrBasicVsr"]
    license_info = family["license"]
    variants = "\n".join(
        "\n".join(
            (
                "    ModelAssetVariant {",
                f"        scale_factor: {variant['scaleFactor']},",
                f"        inference_bytes: {variant['inferenceBytes']},",
                f"        inference_sha256: {json.dumps(variant['inferenceSha256'])},",
                f"        relative_path: {json.dumps(variant['relativePath'])},",
                "    },",
            )
        )
        for variant in family["variants"]
    )
    return (
        "// Generated from contracts/model-assets.json. Do not edit.\n"
        "pub(crate) struct ModelAssetVariant {\n"
        "    pub(crate) scale_factor: u32,\n"
        "    pub(crate) inference_bytes: u64,\n"
        "    pub(crate) inference_sha256: &'static str,\n"
        "    pub(crate) relative_path: &'static str,\n"
        "}\n\n"
        "pub(crate) const REAL_RAWVSR_BASICVSR_LICENSE_PATH: &str =\n"
        f"    {json.dumps(license_info['licenseRelativePath'])};\n"
        f"pub(crate) const REAL_RAWVSR_BASICVSR_NOTICE_PATH: &str = {json.dumps(license_info['noticeRelativePath'])};\n"
        "pub(crate) const REAL_RAWVSR_BASICVSR_VARIANTS: &[ModelAssetVariant] = &[\n"
        f"{variants}\n"
        "];\n"
    )
