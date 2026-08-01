"""Validate and render the neutral application-defaults contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def load_application_defaults(contracts_dir: Path) -> dict[str, Any]:
    """Load application defaults after validating their strict data contract."""

    schema_path = contracts_dir / "application-defaults.schema.json"
    data_path = contracts_dir / "application-defaults.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    defaults = json.loads(data_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    base_uri = "https://vp-workbench.local/contracts/"
    registry = Registry().with_resources(
        (
            f"{base_uri}{path.name}",
            Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in contracts_dir.glob("*.schema.json")
    )
    Draft202012Validator(schema, registry=registry).validate(defaults)
    return defaults


def _python_literal(value: object) -> str:
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


def render_python_application_defaults(defaults: dict[str, Any]) -> str:
    interpolation = defaults["interpolation"]
    super_resolution = defaults["superResolution"]
    workflow = defaults["workflow"]
    output = defaults["output"]
    constants = (
        ("DEFAULT_RIFE_ALGORITHM", interpolation["algorithm"]),
        ("DEFAULT_RIFE_MODEL_VERSION", interpolation["model"]),
        ("DEFAULT_RIFE_ONNX_MODEL", interpolation["onnxModel"]),
        ("DEFAULT_RIFE_TARGET_FPS", interpolation["targetFps"]),
        ("DEFAULT_RIFE_MULTI", interpolation["multi"]),
        ("DEFAULT_RIFE_SCALE", interpolation["scale"]),
        ("DEFAULT_RIFE_FP16", interpolation["fp16"]),
        ("DEFAULT_RIFE_TENSOR_BACKEND", interpolation["tensorBackend"]),
        ("DEFAULT_RIFE_ENGINE", interpolation["engine"]),
        ("DEFAULT_SR_ALGORITHM", super_resolution["algorithm"]),
        ("DEFAULT_SR_ONNX_MODEL", super_resolution["onnxModel"]),
        ("DEFAULT_SR_SCALE_FACTOR", super_resolution["scaleFactor"]),
        ("DEFAULT_SR_NUM_FRAMES", super_resolution["numFrames"]),
        ("DEFAULT_SR_TENSOR_BACKEND", super_resolution["tensorBackend"]),
        ("DEFAULT_SR_ENGINE", super_resolution["engine"]),
        ("DEFAULT_CLI_FPS_MODE", workflow["cliFpsMode"]),
        ("DEFAULT_PROCESS_ORDER", workflow["processOrder"]),
        ("DEFAULT_SEGMENT_FRAMES", output["segmentFrames"]),
    )
    lines = [
        '"""Generated from contracts/application-defaults.json. Do not edit."""',
        "",
        "from typing import Final",
        "",
        *(f"{name}: Final = {_python_literal(value)}" for name, value in constants),
        "",
    ]
    return "\n".join(lines)


def render_typescript_application_defaults(defaults: dict[str, Any]) -> str:
    product_defaults = {key: value for key, value in defaults.items() if key != "$schema"}
    serialized = json.dumps(product_defaults, ensure_ascii=False, indent=2)
    return (
        "// Generated from contracts/application-defaults.json. Do not edit.\n"
        f"export const APPLICATION_DEFAULTS = {serialized} as const\n"
    )


def render_rust_application_defaults(defaults: dict[str, Any]) -> str:
    model_version = json.dumps(defaults["interpolation"]["model"])
    return (
        "// Generated from contracts/application-defaults.json. Do not edit.\n"
        f"pub(crate) const DEFAULT_RIFE_MODEL_VERSION: &str = {model_version};\n"
    )
