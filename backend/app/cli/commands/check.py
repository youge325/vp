"""``python -m app check`` handler."""

from __future__ import annotations

import argparse

from app.cli.probes import (
    _check_onnxruntime_in_subprocess,
    _check_paddle_in_subprocess,
    _check_pytorch_in_subprocess,
)
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

    pytorch_result = _check_pytorch_in_subprocess()
    paddle_result = _check_paddle_in_subprocess()
    onnx_result = _check_onnxruntime_in_subprocess()
    gpu_adapters = list_gpu_adapters()
    public_gpu_adapters = [{"name": adapter["name"], "vendor": adapter["vendor"]} for adapter in gpu_adapters]
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

    # 构建推理引擎支持信息
    tensor_engines: dict[str, list[str]] = {
        "pytorch": [],
        "paddle": [],
        "onnx": [],
    }
    if pytorch_result.get("pytorch_available"):
        engines = []
        if pytorch_result.get("supports_cuda"):
            engines.append("cuda")
        if pytorch_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        tensor_engines["pytorch"] = engines
    if paddle_result.get("paddle_available"):
        engines = []
        if paddle_result.get("supports_cuda"):
            engines.append("cuda")
        if paddle_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        if paddle_result.get("supports_dcu"):
            engines.append("dcu")
        tensor_engines["paddle"] = engines
    if onnx_result.get("onnx_available"):
        engines = []
        if onnx_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        if onnx_result.get("supports_cuda"):
            engines.append("cuda")
        tensor_engines["onnx"] = engines

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
        gpu={"adapters": public_gpu_adapters},
        tensorEngines=tensor_engines,
        interpolationAlgorithms=interpolation_algorithms_payload,
        superResolutionAlgorithms=super_resolution_algorithms_payload,
        runtimeMode=settings.runtime_mode,
    )
