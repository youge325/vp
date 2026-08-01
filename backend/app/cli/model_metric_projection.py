"""Project neutral model metric specs onto the generated check protocol."""

from __future__ import annotations

from collections.abc import Iterable

from app.catalog.model_metrics import ModelMetricSpec, RuntimeMetricSpec, bounded_analysis_notes
from app.generated.contracts import ModelEngineMetricInfo, ModelMetricInfo, ModelVariantInfo


def _project_runtime_metric(spec: RuntimeMetricSpec) -> ModelEngineMetricInfo:
    return ModelEngineMetricInfo(
        gflopsPerMegapixel=spec.gflops_per_megapixel,
        activationBytesPerMegapixel=spec.activation_bytes_per_megapixel,
        runtimeOverheadBytes=spec.runtime_overhead_bytes,
        runtimeFrameCount=spec.runtime_frame_count,
        inputModulo=spec.input_modulo,
        analysisStatus=spec.analysis_status,
        analysisNotes=list(bounded_analysis_notes(spec.analysis_notes)),
    )


def _project_model_metric(spec: ModelMetricSpec) -> ModelVariantInfo:
    runtime = spec.runtime
    return ModelVariantInfo(
        name=spec.name,
        label=spec.label,
        metrics=ModelMetricInfo(
            parameterCount=spec.parameter_count,
            parameterBytes=spec.parameter_bytes,
            gflopsPerMegapixel=runtime.gflops_per_megapixel,
            activationBytesPerMegapixel=runtime.activation_bytes_per_megapixel,
            runtimeOverheadBytes=runtime.runtime_overhead_bytes,
            runtimeFrameCount=runtime.runtime_frame_count,
            inputModulo=runtime.input_modulo,
            analysisStatus=runtime.analysis_status,
            analysisNotes=list(bounded_analysis_notes(runtime.analysis_notes)),
            engineMetrics={name: _project_runtime_metric(engine) for name, engine in spec.engine_metrics},
        ),
    )


def project_model_metrics(specs: Iterable[ModelMetricSpec]) -> list[ModelVariantInfo]:
    return [_project_model_metric(spec) for spec in specs]
