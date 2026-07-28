"""Model metric metadata and lightweight ONNX analysis."""

from __future__ import annotations

from math import prod
from pathlib import Path
from typing import Any

from app.catalog.rife_models import MODEL_SPECS, SUPPORTED_MODELS

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
    "4.13": 5_387_808,
    "4.14": 5_387_808,
    "4.14.lite": 2_991_648,
    "4.15": 5_387_808,
    "4.17": 5_387_808,
    "4.18": 5_387_808,
    "4.19": 5_387_808,
    "4.20": 15_400_008,
    "4.15.lite": 2_622_592,
    "4.16.lite": 2_622_592,
    "4.17.lite": 2_622_592,
    "4.21": 9_345_912,
    "4.22": 9_345_912,
    "4.23": 9_345_912,
    "4.24": 5_387_808,
    "4.22.lite": 4_872_168,
    "4.25": 5_670_892,
    "4.26": 5_670_892,
    "4.25.heavy": 21_669_644,
    "4.25.lite": 5_628_816,
    "4.26.heavy": 5_723_156,
}

_RIFE_RUNTIME_OVERHEAD_BYTES = 38_000_000
_RIFE_TENSORRT_RUNTIME_OVERHEAD_BYTES = 11_000_000
_RIFE_TENSORRT_ACTIVATION_BYTES_PER_MEGAPIXEL = 125_000_000.0
_RIFE_TENSORRT_ACTIVATION_SCALE = 0.18
_RIFE_ACTIVATION_BYTES_PER_MEGAPIXEL: dict[str, float] = {
    "4.0": 353_125_260.0,
    "4.1": 353_125_260.0,
    "4.2": 353_224_219.0,
    "4.3": 353_224_219.0,
    "4.4": 353_224_219.0,
    "4.5": 350_639_583.0,
    "4.6": 349_972_569.0,
    "4.7": 577_089_062.0,
    "4.8": 577_089_062.0,
    "4.9": 577_089_062.0,
    "4.10": 769_180_556.0,
    "4.11": 769_180_556.0,
    "4.12": 769_180_556.0,
    "4.12.lite": 566_835_417.0,
    "4.13.lite": 566_835_417.0,
    "4.13": 735_047_222.0,
    "4.14": 735_047_222.0,
    "4.14.lite": 775_669_444.0,
    "4.15": 735_047_222.0,
    "4.17": 735_047_222.0,
    "4.18": 735_047_222.0,
    "4.19": 735_047_222.0,
    "4.20": 733_946_354.0,
    "4.15.lite": 567_500_694.0,
    "4.16.lite": 567_500_694.0,
    "4.17.lite": 567_500_694.0,
    "4.21": 819_817_535.0,
    "4.22": 819_817_535.0,
    "4.23": 819_817_535.0,
    "4.24": 689_536_111.0,
    "4.22.lite": 712_103_993.0,
    "4.25": 694_800_000.0,
    "4.26": 990_592_795.0,
    "4.25.heavy": 1_018_864_323.0,
    "4.25.lite": 1_162_172_569.0,
    "4.26.heavy": 1_524_014_497.0,
}

_RIFE_TENSORRT_CALIBRATED_METRICS: dict[str, dict[str, Any]] = {
    "4.25": {
        "runtime_overhead_bytes": 10_922_014,
        "activation_bytes_per_megapixel": 124_878_049.0,
        "analysis_status": "ok",
        "analysis_notes": [
            "TensorRT fp32 memory calibrated with torch.cuda max_memory_reserved on 128x128 and 640x288 inputs.",
        ],
    },
    "4.25.lite": {
        "runtime_overhead_bytes": 11_090_318,
        "activation_bytes_per_megapixel": 124_878_049.0,
        "analysis_status": "ok",
        "analysis_notes": [
            "TensorRT fp32 memory calibrated with torch.cuda max_memory_reserved on 128x128 and 640x288 inputs.",
        ],
    },
}

_PADDLEGAN_MODEL_METRICS: dict[str, dict[str, Any]] = {
    "ppmsvsr": {
        "label": "PP-MSVSR",
        "parameter_count": 1_453_607,
        "gflops_per_megapixel": 120.0,
        "runtime_overhead_bytes": 2_391_117_604,
        "activation_bytes_per_megapixel": 1_981_031_424.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 3_688_504_346.0,
        "runtime_frame_count": None,
        "analysis_notes": [
            "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; upper-envelope fit covers 1/2/5/10 frame chunks.",
        ],
        "tensorrt_analysis_notes": [
            "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks.",
        ],
    },
    "ppmsvsr-large": {
        "label": "PP-MSVSR-L",
        "parameter_count": 7_417_197,
        "gflops_per_megapixel": 180.0,
        "runtime_overhead_bytes": 4_038_214_561,
        "activation_bytes_per_megapixel": 3_286_435_185.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 7_318_741_553.0,
        "runtime_frame_count": None,
        "analysis_notes": [
            "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; 10-frame chunk exhausted an 8GB GPU, fit covers 1/2/5 frame chunks.",
        ],
        "tensorrt_analysis_notes": [
            "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks.",
        ],
    },
    "edvr": {
        "label": "EDVR",
        "parameter_count": 20_633_827,
        "gflops_per_megapixel": 240.0,
        "runtime_overhead_bytes": 84_074_752,
        "activation_bytes_per_megapixel": 7_300_784_570.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 6_071_083_459.0,
        "runtime_frame_count": 5,
        "analysis_notes": [
            "EDVR uses a fixed 5-frame neighbor window; calibrated with Paddle CUDA max_memory_reserved on 640x288 input.",
        ],
        "tensorrt_analysis_notes": [
            "EDVR TensorRT memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs; runtime frame count remains 5.",
        ],
    },
    "basicvsr": {
        "label": "BasicVSR",
        "parameter_count": 6_291_311,
        "gflops_per_megapixel": 95.0,
        "runtime_overhead_bytes": 3_106_340_292,
        "activation_bytes_per_megapixel": 616_089_236.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 4_601_300_352.0,
        "runtime_frame_count": None,
        "analysis_notes": [
            "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; upper-envelope fit covers 1/2/5/10 frame chunks.",
        ],
        "tensorrt_analysis_notes": [
            "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks.",
        ],
    },
    "iconvsr": {
        "label": "IconVSR",
        "parameter_count": 8_694_991,
        "gflops_per_megapixel": 130.0,
        "runtime_overhead_bytes": 3_685_021_892,
        "activation_bytes_per_megapixel": 831_528_333.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 5_640_527_435.0,
        "runtime_frame_count": None,
        "analysis_notes": [
            "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; 1/2 frame chunks are below IconVSR's runtime indexing window.",
        ],
        "tensorrt_analysis_notes": [
            "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks.",
        ],
    },
    "basicvsr-plus-plus": {
        "label": "BasicVSR++",
        "parameter_count": 7_322_927,
        "gflops_per_megapixel": 150.0,
        "runtime_overhead_bytes": 4_627_868_420,
        "activation_bytes_per_megapixel": 947_124_479.0,
        "tensorrt_runtime_overhead_bytes": 0,
        "tensorrt_activation_bytes_per_megapixel": 7_484_010_352.0,
        "runtime_frame_count": None,
        "analysis_notes": [
            "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; upper-envelope fit covers 1/2/5/10 frame chunks.",
        ],
        "tensorrt_analysis_notes": [
            "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks.",
        ],
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
    runtime_overhead_bytes: int | None,
    runtime_frame_count: int | None,
    input_modulo: int | None,
    analysis_status: AnalysisStatus,
    analysis_notes: list[str] | None = None,
    engine_metrics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "parameterCount": parameter_count,
        "parameterBytes": parameter_bytes,
        "gflopsPerMegapixel": gflops_per_megapixel,
        "activationBytesPerMegapixel": activation_bytes_per_megapixel,
        "runtimeOverheadBytes": runtime_overhead_bytes,
        "runtimeFrameCount": runtime_frame_count,
        "inputModulo": input_modulo,
        "analysisStatus": analysis_status,
        "analysisNotes": analysis_notes or [],
        "engineMetrics": engine_metrics or {},
    }


def _engine_metric(
    *,
    gflops_per_megapixel: float | None = None,
    activation_bytes_per_megapixel: float | None = None,
    runtime_overhead_bytes: int | None = None,
    runtime_frame_count: int | None = None,
    input_modulo: int | None = None,
    analysis_status: AnalysisStatus = "unknown",
    analysis_notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "gflopsPerMegapixel": gflops_per_megapixel,
        "activationBytesPerMegapixel": activation_bytes_per_megapixel,
        "runtimeOverheadBytes": runtime_overhead_bytes,
        "runtimeFrameCount": runtime_frame_count,
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


def _rife_tensorrt_engine_metric(version: str, gflops_per_megapixel: float) -> dict[str, Any]:
    calibrated = _RIFE_TENSORRT_CALIBRATED_METRICS.get(version)
    if calibrated is not None:
        return _engine_metric(
            gflops_per_megapixel=gflops_per_megapixel,
            activation_bytes_per_megapixel=float(calibrated["activation_bytes_per_megapixel"]),
            runtime_overhead_bytes=int(calibrated["runtime_overhead_bytes"]),
            runtime_frame_count=None,
            input_modulo=MODEL_SPECS[version].modulo,
            analysis_status=str(calibrated["analysis_status"]),
            analysis_notes=list(calibrated["analysis_notes"]),
        )

    activation = max(
        _RIFE_TENSORRT_ACTIVATION_BYTES_PER_MEGAPIXEL,
        _RIFE_ACTIVATION_BYTES_PER_MEGAPIXEL[version] * _RIFE_TENSORRT_ACTIVATION_SCALE,
    )
    return _engine_metric(
        gflops_per_megapixel=gflops_per_megapixel,
        activation_bytes_per_megapixel=round(activation),
        runtime_overhead_bytes=_RIFE_TENSORRT_RUNTIME_OVERHEAD_BYTES,
        runtime_frame_count=None,
        input_modulo=MODEL_SPECS[version].modulo,
        analysis_status="partial",
        analysis_notes=[
            "TensorRT memory estimated from representative RIFE TensorRT calibration; this model was not individually compiled.",
        ],
    )


def get_rife_model_details() -> list[dict[str, Any]]:
    """Return static metric details for built-in RIFE model versions."""
    details: list[dict[str, Any]] = []
    for version in SUPPORTED_MODELS:
        parameter_count = _RIFE_PARAMETER_COUNTS[version]
        gflops_per_megapixel = _rife_gflops_per_megapixel(version, parameter_count)
        details.append(
            _variant(
                version,
                f"RIFE {version}",
                _metrics(
                    parameter_count=parameter_count,
                    parameter_bytes=parameter_count * 4,
                    gflops_per_megapixel=gflops_per_megapixel,
                    activation_bytes_per_megapixel=_RIFE_ACTIVATION_BYTES_PER_MEGAPIXEL[version],
                    runtime_overhead_bytes=_RIFE_RUNTIME_OVERHEAD_BYTES,
                    runtime_frame_count=None,
                    input_modulo=MODEL_SPECS[version].modulo,
                    analysis_status="ok",
                    engine_metrics={
                        "tensorrt": _rife_tensorrt_engine_metric(version, gflops_per_megapixel),
                    },
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
            runtime_overhead_bytes=int(metric["runtime_overhead_bytes"]),
            runtime_frame_count=metric["runtime_frame_count"],
            input_modulo=4,
            analysis_status="ok",
            analysis_notes=list(metric["analysis_notes"]),
            engine_metrics={
                "tensorrt": _engine_metric(
                    gflops_per_megapixel=float(metric["gflops_per_megapixel"]),
                    activation_bytes_per_megapixel=float(metric["tensorrt_activation_bytes_per_megapixel"]),
                    runtime_overhead_bytes=int(metric["tensorrt_runtime_overhead_bytes"]),
                    runtime_frame_count=metric["runtime_frame_count"],
                    input_modulo=4,
                    analysis_status="ok",
                    analysis_notes=list(metric["tensorrt_analysis_notes"]),
                ),
            },
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
            runtime_overhead_bytes=None,
            runtime_frame_count=None,
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
            runtime_overhead_bytes=None,
            runtime_frame_count=None,
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
