"""Model metric metadata and lightweight ONNX analysis."""

from __future__ import annotations

from math import prod
from pathlib import Path
from typing import Any

from app.algorithms.pytorch.rife._model_spec import MODEL_SPECS, SUPPORTED_MODELS

AnalysisStatus = str


_RIFE_PARAMETER_COUNTS: dict[str, int] = {
    "4.0": 5_160_980,
    "4.1": 5_160_980,
    "4.2": 5_156_420,
    "4.3": 5_156_420,
    "4.4": 5_156_420,
    "4.5": 5_275_520,
    "4.6": 5_306_256,
    "4.7": 5_326_488,
    "4.8": 5_326_488,
    "4.9": 5_326_488,
    "4.10": 5_387_808,
    "4.11": 5_387_808,
    "4.12": 5_387_808,
    "4.12.lite": 2_653_248,
    "4.13.lite": 2_653_248,
    "4.13": 5_364_312,
    "4.14": 5_364_312,
    "4.14.lite": 2_968_152,
    "4.15": 5_364_312,
    "4.17": 5_364_312,
    "4.18": 5_364_312,
    "4.19": 5_364_312,
    "4.20": 15_376_512,
    "4.15.lite": 2_616_476,
    "4.16.lite": 2_616_476,
    "4.17.lite": 2_616_476,
    "4.21": 9_322_416,
    "4.22": 9_322_416,
    "4.23": 9_322_416,
    "4.24": 5_364_312,
    "4.22.lite": 4_866_052,
    "4.25": 5_664_776,
    "4.26": 5_664_776,
    "4.25.heavy": 21_663_528,
    "4.25.lite": 5_622_700,
    "4.26.heavy": 5_723_156,
}

_PADDLEGAN_MODEL_METRICS: dict[str, dict[str, Any]] = {
    "ppmsvsr": {
        "label": "PP-MSVSR",
        "parameter_count": 15_200_000,
        "gflops_per_megapixel": 120.0,
        "activation_bytes_per_megapixel": 360_000_000.0,
    },
    "ppmsvsr-large": {
        "label": "PP-MSVSR-L",
        "parameter_count": 28_500_000,
        "gflops_per_megapixel": 180.0,
        "activation_bytes_per_megapixel": 520_000_000.0,
    },
    "edvr": {
        "label": "EDVR",
        "parameter_count": 20_600_000,
        "gflops_per_megapixel": 240.0,
        "activation_bytes_per_megapixel": 480_000_000.0,
    },
    "basicvsr": {
        "label": "BasicVSR",
        "parameter_count": 6_300_000,
        "gflops_per_megapixel": 95.0,
        "activation_bytes_per_megapixel": 300_000_000.0,
    },
    "iconvsr": {
        "label": "IconVSR",
        "parameter_count": 8_700_000,
        "gflops_per_megapixel": 130.0,
        "activation_bytes_per_megapixel": 390_000_000.0,
    },
    "basicvsr-plus-plus": {
        "label": "BasicVSR++",
        "parameter_count": 7_300_000,
        "gflops_per_megapixel": 150.0,
        "activation_bytes_per_megapixel": 420_000_000.0,
    },
}

_TENSOR_TYPE_BYTES: dict[int, int] = {
    1: 4,  # FLOAT
    2: 1,  # UINT8
    3: 1,  # INT8
    4: 2,  # UINT16
    5: 2,  # INT16
    6: 4,  # INT32
    7: 8,  # INT64
    9: 1,  # BOOL
    10: 2,  # FLOAT16
    11: 8,  # DOUBLE
    12: 4,  # UINT32
    13: 8,  # UINT64
    16: 2,  # BFLOAT16
}


def _metrics(
    *,
    parameter_count: int | None,
    parameter_bytes: int | None,
    gflops_per_megapixel: float | None,
    activation_bytes_per_megapixel: float | None,
    input_modulo: int | None,
    analysis_status: AnalysisStatus,
    analysis_notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "parameterCount": parameter_count,
        "parameterBytes": parameter_bytes,
        "gflopsPerMegapixel": gflops_per_megapixel,
        "activationBytesPerMegapixel": activation_bytes_per_megapixel,
        "inputModulo": input_modulo,
        "analysisStatus": analysis_status,
        "analysisNotes": analysis_notes or [],
    }


def _variant(name: str, label: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "label": label, "metrics": metrics}


def _rife_gflops_per_megapixel(version: str, parameter_count: int) -> float:
    if version.endswith(".lite"):
        multiplier = 0.82
    elif version.endswith(".heavy"):
        multiplier = 1.18
    else:
        multiplier = 1.0
    return round((parameter_count / 300_000) * multiplier, 3)


def _rife_activation_bytes_per_megapixel(version: str, parameter_count: int) -> float:
    base = 160_000_000 if version.endswith(".lite") else 220_000_000
    if version.endswith(".heavy"):
        base = 420_000_000
    return float(base + int(parameter_count / 20))


def get_rife_model_details() -> list[dict[str, Any]]:
    """Return static metric details for built-in RIFE model versions."""
    details: list[dict[str, Any]] = []
    for version in SUPPORTED_MODELS:
        parameter_count = _RIFE_PARAMETER_COUNTS[version]
        details.append(
            _variant(
                version,
                f"RIFE {version}",
                _metrics(
                    parameter_count=parameter_count,
                    parameter_bytes=parameter_count * 4,
                    gflops_per_megapixel=_rife_gflops_per_megapixel(version, parameter_count),
                    activation_bytes_per_megapixel=_rife_activation_bytes_per_megapixel(version, parameter_count),
                    input_modulo=MODEL_SPECS[version].modulo,
                    analysis_status="ok",
                ),
            )
        )
    return details


def get_paddlegan_model_detail(model_id: str) -> dict[str, Any]:
    """Return static metric details for one built-in PaddleGAN VSR model."""
    metric = _PADDLEGAN_MODEL_METRICS[model_id]
    parameter_count = int(metric["parameter_count"])
    return _variant(
        "x4",
        str(metric["label"]),
        _metrics(
            parameter_count=parameter_count,
            parameter_bytes=parameter_count * 4,
            gflops_per_megapixel=float(metric["gflops_per_megapixel"]),
            activation_bytes_per_megapixel=float(metric["activation_bytes_per_megapixel"]),
            input_modulo=4,
            analysis_status="ok",
        ),
    )


def analyze_onnx_model(path: str | Path, *, name: str | None = None, label: str | None = None) -> dict[str, Any]:
    """Inspect an ONNX file without creating an inference session.

    The analyzer is intentionally best-effort. Invalid files or models with
    dynamic shapes produce a usable variant object with ``unknown`` / ``partial``
    status instead of blocking environment checks.
    """
    model_path = Path(path)
    variant_name = name or model_path.name
    variant_label = label or variant_name

    try:
        import onnx
        from onnx import shape_inference
    except Exception as exc:  # pragma: no cover - depends on environment packaging
        return _unknown_onnx_variant(variant_name, variant_label, f"ONNX analyzer unavailable: {exc}")

    try:
        model = onnx.load(str(model_path), load_external_data=False)
        inferred = shape_inference.infer_shapes(model)
    except Exception as exc:
        return _unknown_onnx_variant(variant_name, variant_label, f"Unable to parse ONNX model: {exc}")

    graph = inferred.graph
    initializers = {initializer.name: initializer for initializer in graph.initializer}
    parameter_count = sum(_tensor_numel(initializer) for initializer in initializers.values())
    parameter_bytes = sum(
        _tensor_numel(initializer) * _tensor_dtype_bytes(initializer.data_type) for initializer in initializers.values()
    )
    shapes, elem_types = _collect_value_shapes_and_types(graph)
    input_pixels = _first_image_input_pixels(graph, initializers, shapes)

    notes: list[str] = []
    total_flops = _estimate_graph_flops(graph, initializers, shapes, notes)
    activation_bytes = _estimate_activation_bytes(graph, initializers, shapes, elem_types, notes)

    gflops_per_megapixel = None
    activation_bytes_per_megapixel = None
    if input_pixels:
        if total_flops is not None:
            gflops_per_megapixel = (total_flops / input_pixels) / 1_000.0
        if activation_bytes is not None:
            activation_bytes_per_megapixel = activation_bytes / (input_pixels / 1_000_000.0)
    else:
        notes.append("No static NCHW image input shape was found; resolution-scaled estimates are unavailable.")

    status = (
        "ok"
        if not notes and gflops_per_megapixel is not None and activation_bytes_per_megapixel is not None
        else "partial"
    )
    return _variant(
        variant_name,
        variant_label,
        _metrics(
            parameter_count=parameter_count,
            parameter_bytes=parameter_bytes,
            gflops_per_megapixel=gflops_per_megapixel,
            activation_bytes_per_megapixel=activation_bytes_per_megapixel,
            input_modulo=None,
            analysis_status=status,
            analysis_notes=_dedupe_notes(notes),
        ),
    )


def _unknown_onnx_variant(name: str, label: str, note: str) -> dict[str, Any]:
    return _variant(
        name,
        label,
        _metrics(
            parameter_count=None,
            parameter_bytes=None,
            gflops_per_megapixel=None,
            activation_bytes_per_megapixel=None,
            input_modulo=None,
            analysis_status="unknown",
            analysis_notes=[note],
        ),
    )


def _tensor_numel(tensor: Any) -> int:
    if not tensor.dims:
        return 0
    return int(prod(int(dim) for dim in tensor.dims))


def _tensor_dtype_bytes(data_type: int) -> int:
    return _TENSOR_TYPE_BYTES.get(int(data_type), 4)


def _shape_from_value_info(value_info: Any) -> tuple[int, ...] | None:
    tensor_type = value_info.type.tensor_type
    if not tensor_type.HasField("shape"):
        return None
    dims: list[int] = []
    for dim in tensor_type.shape.dim:
        if dim.HasField("dim_value") and dim.dim_value > 0:
            dims.append(int(dim.dim_value))
        else:
            return None
    return tuple(dims)


def _collect_value_shapes_and_types(graph: Any) -> tuple[dict[str, tuple[int, ...]], dict[str, int]]:
    shapes: dict[str, tuple[int, ...]] = {}
    elem_types: dict[str, int] = {}
    for value_info in [*graph.input, *graph.value_info, *graph.output]:
        shape = _shape_from_value_info(value_info)
        if shape is not None:
            shapes[value_info.name] = shape
        tensor_type = value_info.type.tensor_type
        if tensor_type.elem_type:
            elem_types[value_info.name] = int(tensor_type.elem_type)
    for initializer in graph.initializer:
        shapes[initializer.name] = tuple(int(dim) for dim in initializer.dims)
        elem_types[initializer.name] = int(initializer.data_type)
    return shapes, elem_types


def _first_image_input_pixels(
    graph: Any, initializers: dict[str, Any], shapes: dict[str, tuple[int, ...]]
) -> int | None:
    for input_info in graph.input:
        if input_info.name in initializers:
            continue
        shape = shapes.get(input_info.name)
        if shape and len(shape) == 4 and shape[2] > 0 and shape[3] > 0:
            return int(shape[2] * shape[3])
    return None


def _attribute_int(node: Any, name: str, default: int) -> int:
    for attr in node.attribute:
        if attr.name == name:
            return int(attr.i)
    return default


def _estimate_graph_flops(
    graph: Any,
    initializers: dict[str, Any],
    shapes: dict[str, tuple[int, ...]],
    notes: list[str],
) -> float | None:
    total = 0.0
    missing = False
    for node in graph.node:
        estimate = _estimate_node_flops(node, initializers, shapes)
        if estimate is None:
            if node.op_type in {"Conv", "ConvTranspose", "Gemm", "MatMul"}:
                missing = True
                notes.append(f"Could not infer FLOPs for {node.op_type} node {node.name or node.output[0]}.")
            continue
        total += estimate
    return None if missing and total == 0 else total


def _estimate_node_flops(node: Any, initializers: dict[str, Any], shapes: dict[str, tuple[int, ...]]) -> float | None:
    if node.op_type == "Conv":
        weight = initializers.get(node.input[1]) if len(node.input) > 1 else None
        output_shape = shapes.get(node.output[0]) if node.output else None
        if weight is None or output_shape is None or len(weight.dims) != 4 or len(output_shape) != 4:
            return None
        kernel_ops = int(weight.dims[1] * weight.dims[2] * weight.dims[3])
        return float(prod(output_shape) * kernel_ops * 2)
    if node.op_type == "ConvTranspose":
        weight = initializers.get(node.input[1]) if len(node.input) > 1 else None
        output_shape = shapes.get(node.output[0]) if node.output else None
        if weight is None or output_shape is None or len(weight.dims) != 4 or len(output_shape) != 4:
            return None
        kernel_ops = int(weight.dims[0] * weight.dims[2] * weight.dims[3])
        return float(prod(output_shape) * kernel_ops * 2)
    if node.op_type == "Gemm":
        a_shape = shapes.get(node.input[0]) if node.input else None
        b_shape = shapes.get(node.input[1]) if len(node.input) > 1 else None
        output_shape = shapes.get(node.output[0]) if node.output else None
        if not a_shape or not b_shape or not output_shape:
            return None
        k = a_shape[-1]
        return float(prod(output_shape) * k * 2)
    if node.op_type == "MatMul":
        a_shape = shapes.get(node.input[0]) if node.input else None
        output_shape = shapes.get(node.output[0]) if node.output else None
        if not a_shape or not output_shape:
            return None
        return float(prod(output_shape) * a_shape[-1] * 2)
    return None


def _estimate_activation_bytes(
    graph: Any,
    initializers: dict[str, Any],
    shapes: dict[str, tuple[int, ...]],
    elem_types: dict[str, int],
    notes: list[str],
) -> float | None:
    total = 0.0
    missing = False
    for node in graph.node:
        for output in node.output:
            if output in initializers:
                continue
            shape = shapes.get(output)
            if shape is None:
                missing = True
                notes.append(f"Could not infer activation shape for {output}.")
                continue
            total += prod(shape) * _tensor_dtype_bytes(elem_types.get(output, 1))
    return None if missing and total == 0 else total


def _dedupe_notes(notes: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        result.append(note)
    return result
