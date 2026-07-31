"""Immutable calibrated metric catalog for built-in models."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

from app.catalog.rife_models import MODEL_SPECS, SUPPORTED_MODELS

AnalysisStatus = Literal["ok", "partial", "unknown"]

_MAX_ANALYSIS_NOTES = 8
_MAX_ANALYSIS_NOTE_BYTES = 512


def bounded_analysis_notes(notes: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate and bound model diagnostics for the single-line check protocol."""
    result: list[str] = []
    seen: set[str] = set()
    for note in notes:
        encoded = note.encode("utf-8")
        if len(encoded) > _MAX_ANALYSIS_NOTE_BYTES:
            suffix = "… (diagnostic truncated)"
            budget = _MAX_ANALYSIS_NOTE_BYTES - len(suffix.encode("utf-8"))
            note = encoded[:budget].decode("utf-8", errors="ignore") + suffix
        if note in seen:
            continue
        seen.add(note)
        result.append(note)
        if len(result) == _MAX_ANALYSIS_NOTES:
            break
    return tuple(result)


@dataclass(frozen=True, slots=True)
class EngineMetricSpec:
    """Immutable calibrated metrics for one execution engine."""

    gflops_per_megapixel: float | None
    activation_bytes_per_megapixel: float | None
    runtime_overhead_bytes: int | None
    runtime_frame_count: int | None
    input_modulo: int | None
    analysis_status: AnalysisStatus
    analysis_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelMetricSpec:
    """Immutable source record projected to generated wire models on demand."""

    name: str
    label: str
    parameter_count: int | None
    parameter_bytes: int | None
    gflops_per_megapixel: float | None
    activation_bytes_per_megapixel: float | None
    runtime_overhead_bytes: int | None
    runtime_frame_count: int | None
    input_modulo: int | None
    analysis_status: AnalysisStatus
    analysis_notes: tuple[str, ...] = ()
    engine_metrics: tuple[tuple[str, EngineMetricSpec], ...] = ()


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

_RIFE_CALIBRATION_NOTE = (
    "TensorRT fp32 memory calibrated with torch.cuda max_memory_reserved on 128x128 and 640x288 inputs."
)
_RIFE_TENSORRT_CALIBRATIONS: Mapping[str, EngineMetricSpec] = MappingProxyType(
    {
        "4.25": EngineMetricSpec(
            gflops_per_megapixel=None,
            activation_bytes_per_megapixel=124_878_049.0,
            runtime_overhead_bytes=10_922_014,
            runtime_frame_count=None,
            input_modulo=MODEL_SPECS["4.25"].modulo,
            analysis_status="ok",
            analysis_notes=(_RIFE_CALIBRATION_NOTE,),
        ),
        "4.25.lite": EngineMetricSpec(
            gflops_per_megapixel=None,
            activation_bytes_per_megapixel=124_878_049.0,
            runtime_overhead_bytes=11_090_318,
            runtime_frame_count=None,
            input_modulo=MODEL_SPECS["4.25.lite"].modulo,
            analysis_status="ok",
            analysis_notes=(_RIFE_CALIBRATION_NOTE,),
        ),
    }
)

_PADDLE_RUNTIME_NOTE = (
    "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; upper-envelope fit covers 1/2/5/10 frame chunks."
)
_PADDLE_TENSORRT_NOTE = (
    "TensorRT fp32 memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs, 5-frame chunks."
)


def _paddle_metric_spec(
    *,
    label: str,
    parameter_count: int,
    gflops_per_megapixel: float,
    runtime_overhead_bytes: int,
    activation_bytes_per_megapixel: float,
    tensorrt_activation_bytes_per_megapixel: float,
    runtime_frame_count: int | None = None,
    analysis_notes: tuple[str, ...] = (_PADDLE_RUNTIME_NOTE,),
    tensorrt_analysis_notes: tuple[str, ...] = (_PADDLE_TENSORRT_NOTE,),
) -> ModelMetricSpec:
    return ModelMetricSpec(
        name="x4",
        label=label,
        parameter_count=parameter_count,
        parameter_bytes=parameter_count * 4,
        gflops_per_megapixel=gflops_per_megapixel,
        activation_bytes_per_megapixel=activation_bytes_per_megapixel,
        runtime_overhead_bytes=runtime_overhead_bytes,
        runtime_frame_count=runtime_frame_count,
        input_modulo=4,
        analysis_status="ok",
        analysis_notes=analysis_notes,
        engine_metrics=(
            (
                "tensorrt",
                EngineMetricSpec(
                    gflops_per_megapixel=gflops_per_megapixel,
                    activation_bytes_per_megapixel=tensorrt_activation_bytes_per_megapixel,
                    runtime_overhead_bytes=0,
                    runtime_frame_count=runtime_frame_count,
                    input_modulo=4,
                    analysis_status="ok",
                    analysis_notes=tensorrt_analysis_notes,
                ),
            ),
        ),
    )


PADDLEGAN_MODEL_METRIC_SPECS: Mapping[str, ModelMetricSpec] = MappingProxyType(
    {
        "ppmsvsr": _paddle_metric_spec(
            label="PP-MSVSR",
            parameter_count=1_453_607,
            gflops_per_megapixel=120.0,
            runtime_overhead_bytes=2_391_117_604,
            activation_bytes_per_megapixel=1_981_031_424.0,
            tensorrt_activation_bytes_per_megapixel=3_688_504_346.0,
        ),
        "ppmsvsr-large": _paddle_metric_spec(
            label="PP-MSVSR-L",
            parameter_count=7_417_197,
            gflops_per_megapixel=180.0,
            runtime_overhead_bytes=4_038_214_561,
            activation_bytes_per_megapixel=3_286_435_185.0,
            tensorrt_activation_bytes_per_megapixel=7_318_741_553.0,
            analysis_notes=(
                "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; "
                "10-frame chunk exhausted an 8GB GPU, fit covers 1/2/5 frame chunks.",
            ),
        ),
        "edvr": _paddle_metric_spec(
            label="EDVR",
            parameter_count=20_633_827,
            gflops_per_megapixel=240.0,
            runtime_overhead_bytes=84_074_752,
            activation_bytes_per_megapixel=7_300_784_570.0,
            tensorrt_activation_bytes_per_megapixel=6_071_083_459.0,
            runtime_frame_count=5,
            analysis_notes=(
                "EDVR uses a fixed 5-frame neighbor window; calibrated with Paddle CUDA max_memory_reserved "
                "on 640x288 input.",
            ),
            tensorrt_analysis_notes=(
                "EDVR TensorRT memory calibrated with Paddle max_memory_reserved on 128x128 and 640x288 inputs; "
                "runtime frame count remains 5.",
            ),
        ),
        "basicvsr": _paddle_metric_spec(
            label="BasicVSR",
            parameter_count=6_291_311,
            gflops_per_megapixel=95.0,
            runtime_overhead_bytes=3_106_340_292,
            activation_bytes_per_megapixel=616_089_236.0,
            tensorrt_activation_bytes_per_megapixel=4_601_300_352.0,
        ),
        "iconvsr": _paddle_metric_spec(
            label="IconVSR",
            parameter_count=8_694_991,
            gflops_per_megapixel=130.0,
            runtime_overhead_bytes=3_685_021_892,
            activation_bytes_per_megapixel=831_528_333.0,
            tensorrt_activation_bytes_per_megapixel=5_640_527_435.0,
            analysis_notes=(
                "Calibrated with Paddle CUDA max_memory_reserved on 640x288 input; "
                "1/2 frame chunks are below IconVSR's runtime indexing window.",
            ),
        ),
        "basicvsr-plus-plus": _paddle_metric_spec(
            label="BasicVSR++",
            parameter_count=7_322_927,
            gflops_per_megapixel=150.0,
            runtime_overhead_bytes=4_627_868_420,
            activation_bytes_per_megapixel=947_124_479.0,
            tensorrt_activation_bytes_per_megapixel=7_484_010_352.0,
        ),
    }
)


def _rife_gflops_per_megapixel(version: str, parameter_count: int) -> float:
    if version.endswith(".lite"):
        multiplier = 0.82
    elif version.endswith(".heavy"):
        multiplier = 1.18
    else:
        multiplier = 1.0
    return round((parameter_count / 300_000) * multiplier, 3)


def _rife_tensorrt_engine_spec(version: str, gflops_per_megapixel: float) -> EngineMetricSpec:
    calibrated = _RIFE_TENSORRT_CALIBRATIONS.get(version)
    if calibrated is not None:
        return EngineMetricSpec(
            gflops_per_megapixel=gflops_per_megapixel,
            activation_bytes_per_megapixel=calibrated.activation_bytes_per_megapixel,
            runtime_overhead_bytes=calibrated.runtime_overhead_bytes,
            runtime_frame_count=calibrated.runtime_frame_count,
            input_modulo=calibrated.input_modulo,
            analysis_status=calibrated.analysis_status,
            analysis_notes=calibrated.analysis_notes,
        )

    activation = max(
        _RIFE_TENSORRT_ACTIVATION_BYTES_PER_MEGAPIXEL,
        _RIFE_ACTIVATION_BYTES_PER_MEGAPIXEL[version] * _RIFE_TENSORRT_ACTIVATION_SCALE,
    )
    return EngineMetricSpec(
        gflops_per_megapixel=gflops_per_megapixel,
        activation_bytes_per_megapixel=round(activation),
        runtime_overhead_bytes=_RIFE_TENSORRT_RUNTIME_OVERHEAD_BYTES,
        runtime_frame_count=None,
        input_modulo=MODEL_SPECS[version].modulo,
        analysis_status="partial",
        analysis_notes=(
            "TensorRT memory estimated from representative RIFE TensorRT calibration; this model was not individually compiled.",
        ),
    )


def _rife_metric_spec(version: str) -> ModelMetricSpec:
    parameter_count = _RIFE_PARAMETER_COUNTS[version]
    gflops_per_megapixel = _rife_gflops_per_megapixel(version, parameter_count)
    return ModelMetricSpec(
        name=version,
        label=f"RIFE {version}",
        parameter_count=parameter_count,
        parameter_bytes=parameter_count * 4,
        gflops_per_megapixel=gflops_per_megapixel,
        activation_bytes_per_megapixel=_RIFE_ACTIVATION_BYTES_PER_MEGAPIXEL[version],
        runtime_overhead_bytes=_RIFE_RUNTIME_OVERHEAD_BYTES,
        runtime_frame_count=None,
        input_modulo=MODEL_SPECS[version].modulo,
        analysis_status="ok",
        engine_metrics=(("tensorrt", _rife_tensorrt_engine_spec(version, gflops_per_megapixel)),),
    )


RIFE_MODEL_METRIC_SPECS: Mapping[str, ModelMetricSpec] = MappingProxyType(
    {version: _rife_metric_spec(version) for version in SUPPORTED_MODELS}
)

MODEL_METRIC_SPECS_BY_ALGORITHM: Mapping[str, tuple[ModelMetricSpec, ...]] = MappingProxyType(
    {
        "rife": tuple(RIFE_MODEL_METRIC_SPECS[version] for version in SUPPORTED_MODELS),
        **{model_id: (spec,) for model_id, spec in PADDLEGAN_MODEL_METRIC_SPECS.items()},
    }
)
