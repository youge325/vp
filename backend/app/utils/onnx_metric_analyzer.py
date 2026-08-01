"""Best-effort ONNX graph metric analyzer adapter."""

from __future__ import annotations

from collections import Counter
from math import prod
from pathlib import Path
from typing import Any

from app.catalog.model_metrics import ModelMetricSpec, RuntimeMetricSpec, bounded_analysis_notes

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


def analyze_onnx_model(path: str | Path, *, name: str | None = None, label: str | None = None) -> ModelMetricSpec:
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
        return _unknown_onnx_model_variant(variant_name, variant_label, f"ONNX analyzer unavailable: {exc}")

    try:
        model = onnx.load(str(model_path), load_external_data=False)
        inferred = shape_inference.infer_shapes(model)
    except Exception as exc:
        return _unknown_onnx_model_variant(variant_name, variant_label, f"Unable to parse ONNX model: {exc}")

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
    return ModelMetricSpec(
        name=variant_name,
        label=variant_label,
        parameter_count=parameter_count,
        parameter_bytes=parameter_bytes,
        runtime=RuntimeMetricSpec(
            gflops_per_megapixel=gflops_per_megapixel,
            activation_bytes_per_megapixel=activation_bytes_per_megapixel,
            runtime_overhead_bytes=None,
            runtime_frame_count=None,
            input_modulo=None,
            analysis_status=status,
            analysis_notes=bounded_analysis_notes(notes),
        ),
    )


def _unknown_onnx_model_variant(name: str, label: str, note: str) -> ModelMetricSpec:
    return ModelMetricSpec(
        name=name,
        label=label,
        parameter_count=None,
        parameter_bytes=None,
        runtime=RuntimeMetricSpec(
            gflops_per_megapixel=None,
            activation_bytes_per_megapixel=None,
            runtime_overhead_bytes=None,
            runtime_frame_count=None,
            input_modulo=None,
            analysis_status="unknown",
            analysis_notes=bounded_analysis_notes((note,)),
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


def _estimate_graph_flops(
    graph: Any,
    initializers: dict[str, Any],
    shapes: dict[str, tuple[int, ...]],
    notes: list[str],
) -> float | None:
    total = 0.0
    missing = False
    missing_by_operator: Counter[str] = Counter()
    for node in graph.node:
        estimate = _estimate_node_flops(node, initializers, shapes)
        if estimate is None:
            if node.op_type in {"Conv", "ConvTranspose", "Gemm", "MatMul"}:
                missing = True
                missing_by_operator[node.op_type] += 1
            continue
        total += estimate
    for operator, count in sorted(missing_by_operator.items()):
        notes.append(f"Could not infer FLOPs for {count} {operator} node{'s' if count != 1 else ''}.")
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
    missing_count = 0
    for node in graph.node:
        for output in node.output:
            if output in initializers:
                continue
            shape = shapes.get(output)
            if shape is None:
                missing = True
                missing_count += 1
                continue
            total += prod(shape) * _tensor_dtype_bytes(elem_types.get(output, 1))
    if missing_count:
        notes.append(f"Could not infer activation shapes for {missing_count} graph outputs.")
    return None if missing and total == 0 else total
