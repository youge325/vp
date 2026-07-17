"""``python -m app check`` handler."""

from __future__ import annotations

import argparse

from app.cli.probes import probe_tensor_engines
from app.config import settings
from app.processing.interpolation import SUPPORTED_ALGORITHMS as INTERPOLATION_ALGORITHMS
from app.processing.super_resolution import SUPPORTED_ALGORITHMS as SR_ALGORITHMS
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.onnx_models import scan_onnx_model_details, scan_onnx_models
from app.utils.system_probe import list_gpu_adapters


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
        else {
            "hwaccels": [],
            "encoderProfiles": [],
            "decoderProfiles": [],
        }
    )

    interpolation_algorithms_payload = [
        {
            **alg,
            "onnxModels": onnx_models.get("interpolation", {}).get(alg["name"], []),
            "onnxModelDetails": onnx_model_details.get("interpolation", {}).get(alg["name"], []),
        }
        for alg in INTERPOLATION_ALGORITHMS
    ]
    super_resolution_algorithms_payload = [
        {
            **alg,
            "onnxModels": onnx_models.get("super_resolution", {}).get(alg["name"], []),
            "onnxModelDetails": onnx_model_details.get("super_resolution", {}).get(alg["name"], []),
        }
        for alg in SR_ALGORITHMS
    ]

    ndjson.check(
        ffmpeg={
            "available": ffmpeg_available,
            "hwaccels": ffmpeg_capabilities["hwaccels"],
            "encoderProfiles": ffmpeg_capabilities["encoderProfiles"],
            "decoderProfiles": ffmpeg_capabilities["decoderProfiles"],
        },
        gpu={"adapters": gpu_adapters},
        tensorEngines=tensor_engines,
        interpolationAlgorithms=interpolation_algorithms_payload,
        superResolutionAlgorithms=super_resolution_algorithms_payload,
        runtimeMode=settings.runtime_mode,
    )
