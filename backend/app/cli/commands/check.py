"""``python -m app check`` handler."""

from __future__ import annotations

import argparse
from typing import cast

from app.cli.probes import probe_tensor_engines
from app.config import settings
from app.generated.contracts import (
    AlgorithmFamily,
    AlgorithmInfo,
    EnvironmentCheckResult,
    FfmpegInfo,
    GpuAdapter,
    GpuInfo,
    GpuVendor,
    InferenceEngine,
    InputFrameMode,
    ModelVariantInfo,
    TensorBackend,
    TensorEngines,
)
from app.generated.protocol_constants import BackendEnvelopeType
from app.processing.interpolation import SUPPORTED_ALGORITHMS as INTERPOLATION_ALGORITHMS
from app.processing.super_resolution import SUPPORTED_ALGORITHMS as SR_ALGORITHMS
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.onnx_models import scan_onnx_model_details, scan_onnx_models
from app.utils.system_probe import list_gpu_adapters


def _algorithm_payload(
    algorithm: dict[str, object],
    *,
    onnx_models: list[str],
    onnx_model_details: list[ModelVariantInfo],
) -> AlgorithmInfo:
    """Project catalog entries onto the complete version-2 wire contract."""
    raw_fixed_scale_factor = cast(int | float | None, algorithm.get("fixedScaleFactor"))
    fixed_scale_factor = int(raw_fixed_scale_factor) if raw_fixed_scale_factor is not None else None
    return AlgorithmInfo(
        name=cast(str, algorithm["name"]),
        family=AlgorithmFamily(cast(str, algorithm["family"])),
        tensor_backends=[TensorBackend(backend) for backend in cast(list[str], algorithm.get("tensorBackends", []))],
        models=list(cast(list[str], algorithm.get("models", []))),
        onnx_models=onnx_models,
        model_details=list(cast(list[ModelVariantInfo], algorithm.get("modelDetails", []))),
        onnx_model_details=onnx_model_details,
        scale_factors=[
            int(scale_factor) for scale_factor in cast(list[int | float], algorithm.get("scaleFactors", []))
        ],
        fixed_scale_factor=fixed_scale_factor,
        default_num_frames=cast(int | None, algorithm.get("defaultNumFrames")),
        input_frame_mode=InputFrameMode(cast(str, algorithm["inputFrameMode"])),
    )


def cmd_check(_args: argparse.Namespace) -> None:
    ffmpeg = FFmpegWrapper()
    ffmpeg_available = ffmpeg.is_available()

    tensor_engines = probe_tensor_engines()
    gpu_adapters = list_gpu_adapters()
    onnx_models = scan_onnx_models(settings.RIFE_MODEL_DIR)
    onnx_model_details = scan_onnx_model_details(settings.RIFE_MODEL_DIR)
    ffmpeg_capabilities = (
        ffmpeg.discover_capabilities(gpu_adapters)
        if ffmpeg_available
        else FfmpegInfo(available=False, hwaccels=[], encoderProfiles=[], decoderProfiles=[])
    )

    interpolation_algorithms_payload = [
        _algorithm_payload(
            alg,
            onnx_models=onnx_models.get("interpolation", {}).get(alg["name"], []),
            onnx_model_details=onnx_model_details.get("interpolation", {}).get(alg["name"], []),
        )
        for alg in INTERPOLATION_ALGORITHMS
    ]
    super_resolution_algorithms_payload = [
        _algorithm_payload(
            alg,
            onnx_models=onnx_models.get("super_resolution", {}).get(alg["name"], []),
            onnx_model_details=onnx_model_details.get("super_resolution", {}).get(alg["name"], []),
        )
        for alg in SR_ALGORITHMS
    ]

    ndjson.emit(
        BackendEnvelopeType.CHECK,
        EnvironmentCheckResult(
            ffmpeg=ffmpeg_capabilities,
            gpu=GpuInfo(
                adapters=[
                    GpuAdapter(
                        name=adapter["name"],
                        vendor=GpuVendor(adapter["vendor"]),
                    )
                    for adapter in gpu_adapters
                ]
            ),
            tensor_engines=TensorEngines(
                pytorch=[InferenceEngine(engine) for engine in tensor_engines["pytorch"]],
                paddle=[InferenceEngine(engine) for engine in tensor_engines["paddle"]],
                onnx=[InferenceEngine(engine) for engine in tensor_engines["onnx"]],
            ),
            interpolationAlgorithms=interpolation_algorithms_payload,
            superResolutionAlgorithms=super_resolution_algorithms_payload,
            runtimeMode=settings.runtime_mode,
        ),
    )
