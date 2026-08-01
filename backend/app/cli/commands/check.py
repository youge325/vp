"""``python -m app check`` handler."""

from __future__ import annotations

import argparse

from app.catalog.algorithm_capabilities import (
    AlgorithmCapability,
    INTERPOLATION_CAPABILITIES,
    SUPER_RESOLUTION_CAPABILITIES,
    project_dynamic_onnx_super_resolution_capabilities,
)
from app.catalog.model_metrics import MODEL_METRIC_SPECS_BY_ALGORITHM, ModelMetricSpec
from app.cli.model_metric_projection import project_model_metrics
from app.cli.probes import probe_tensor_engines
from app.config import settings
from app.generated.contracts import (
    AlgorithmFamily,
    AlgorithmInfo,
    EnvironmentCheckResult,
    FfmpegInfo,
    GpuInfo,
    InputFrameMode,
    TensorBackend,
)
from app.generated.protocol_constants import BackendEnvelopeType
from app.protocol.emitter import ndjson
from app.utils.ffmpeg.capabilities import discover_capabilities
from app.utils.ffmpeg.media_probe import is_available
from app.utils.onnx_models import scan_onnx_catalog
from app.utils.system_probe import list_gpu_adapters


def _algorithm_payload(
    algorithm: AlgorithmCapability,
    *,
    onnx_models: list[str],
    onnx_model_details: list[ModelMetricSpec],
) -> AlgorithmInfo:
    """Project one neutral catalog entry onto the generated wire contract."""
    fixed_scale_factor = algorithm.descriptor.fixed_scale_factor
    return AlgorithmInfo(
        name=algorithm.name,
        family=AlgorithmFamily(algorithm.descriptor.model_kind),
        tensor_backends=[TensorBackend(backend) for backend in sorted(algorithm.descriptor.supported_backends)],
        models=list(algorithm.models),
        onnx_models=onnx_models,
        model_details=project_model_metrics(MODEL_METRIC_SPECS_BY_ALGORITHM.get(algorithm.name, ())),
        onnx_model_details=project_model_metrics(onnx_model_details),
        fixed_scale_factor=int(fixed_scale_factor) if fixed_scale_factor is not None else None,
        default_num_frames=algorithm.default_num_frames,
        input_frame_mode=InputFrameMode(algorithm.input_frame_mode),
    )


def cmd_check(_args: argparse.Namespace) -> None:
    ffmpeg_available = is_available(settings.FFMPEG_PATH)

    tensor_engines = probe_tensor_engines()
    gpu_adapters = list_gpu_adapters()
    onnx_catalog = scan_onnx_catalog(settings.RIFE_MODEL_DIR)
    onnx_models = onnx_catalog.names
    onnx_model_details = onnx_catalog.details
    ffmpeg_capabilities = (
        discover_capabilities(settings.FFMPEG_PATH, gpu_adapters)
        if ffmpeg_available
        else FfmpegInfo(available=False, hwaccels=[], encoderProfiles=[], decoderProfiles=[])
    )

    interpolation_algorithms_payload = [
        _algorithm_payload(
            alg,
            onnx_models=onnx_models.get("interpolation", {}).get(alg.name, []),
            onnx_model_details=onnx_model_details.get("interpolation", {}).get(alg.name, []),
        )
        for alg in INTERPOLATION_CAPABILITIES
    ]
    discovered_super_resolution = onnx_models.get("super_resolution", {})
    super_resolution_capabilities = (
        *SUPER_RESOLUTION_CAPABILITIES,
        *project_dynamic_onnx_super_resolution_capabilities(discovered_super_resolution),
    )
    super_resolution_algorithms_payload = [
        _algorithm_payload(
            alg,
            onnx_models=(
                discovered_super_resolution.get(alg.name, [])
                if alg.descriptor.factory_key == "onnx_super_resolution"
                else []
            ),
            onnx_model_details=(
                onnx_model_details.get("super_resolution", {}).get(alg.name, [])
                if alg.descriptor.factory_key == "onnx_super_resolution"
                else []
            ),
        )
        for alg in super_resolution_capabilities
    ]

    ndjson.emit(
        BackendEnvelopeType.CHECK,
        EnvironmentCheckResult(
            ffmpeg=ffmpeg_capabilities,
            gpu=GpuInfo(adapters=gpu_adapters),
            tensor_engines=tensor_engines,
            interpolationAlgorithms=interpolation_algorithms_payload,
            superResolutionAlgorithms=super_resolution_algorithms_payload,
            runtimeMode=settings.runtime_mode,
        ),
    )
