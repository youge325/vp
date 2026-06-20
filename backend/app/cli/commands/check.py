"""``python -m app check`` handler."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.cli.probes import (
    _check_onnxruntime_in_subprocess,
    _check_paddle_in_subprocess,
    _check_pytorch_in_subprocess,
)
from app.config import settings
from app.processing.anime_optimization import SUPPORTED_PROFILES as ANIME_PROFILES
from app.processing.interpolation import SUPPORTED_ALGORITHMS as INTERPOLATION_ALGORITHMS
from app.processing.super_resolution import SUPPORTED_ALGORITHMS as SR_ALGORITHMS
from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS, resolve_weight_path
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.onnx_models import scan_onnx_models
from app.utils.system_probe import list_gpu_adapters


def cmd_check(_args: argparse.Namespace) -> None:
    ffmpeg = FFmpegWrapper()
    ffmpeg_available = ffmpeg.is_available()
    ffmpeg_version = ffmpeg.get_version() if ffmpeg_available else ""

    pytorch_result = _check_pytorch_in_subprocess()
    paddle_result = _check_paddle_in_subprocess()
    onnx_result = _check_onnxruntime_in_subprocess()
    gpu_adapters = list_gpu_adapters()
    non_virtual_adapters = [adapter for adapter in gpu_adapters if adapter.get("device_type") != "virtual"]

    default_model_path = Path(settings.RIFE_MODEL_DIR) / "interpolation" / "rife" / "rife_v4.25.onnx"
    default_model_available = default_model_path.is_file() and default_model_path.stat().st_size > 0
    onnx_models = scan_onnx_models(settings.RIFE_MODEL_DIR)
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
    tensor_engines: dict[str, list[str]] = {}
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

    # 构建后端设备兼容性矩阵
    backend_device_support: dict[str, list[str]] = {
        "pytorch": ["nvidia", "intel", "amd"],
        "paddle": ["nvidia", "intel", "amd", "hygon"],
        "onnx": ["nvidia", "intel", "amd"],
    }

    interpolation_algorithms_payload = [
        {**alg, "onnxModels": onnx_models.get("interpolation", {}).get(alg["name"], [])}
        for alg in INTERPOLATION_ALGORITHMS
    ]
    super_resolution_algorithms_payload = []
    for alg in SR_ALGORITHMS:
        payload = {**alg, "onnxModels": onnx_models.get("super_resolution", {}).get(alg["name"], [])}
        if alg["name"] in PADDLEGAN_VSR_SPECS:
            weight_path = resolve_weight_path(alg["name"])
            payload.update(
                {
                    "weightPath": str(weight_path),
                    "weightAvailable": weight_path.is_file() and weight_path.stat().st_size > 0,
                }
            )
        super_resolution_algorithms_payload.append(payload)

    ndjson.check(
        ffmpeg={
            "available": ffmpeg_available,
            "path": ffmpeg.ffmpeg_path,
            "ffprobePath": ffmpeg.ffprobe_path,
            "version": ffmpeg_version,
            "hwaccels": ffmpeg_capabilities["hwaccels"],
            "encoderProfiles": ffmpeg_capabilities["encoderProfiles"],
            "decoderProfiles": ffmpeg_capabilities["decoderProfiles"],
        },
        gpu={
            "available": bool(non_virtual_adapters),
            "devices": [adapter["name"] for adapter in non_virtual_adapters],
            "adapters": gpu_adapters,
            "cudaAvailable": pytorch_result["gpu_available"],
        },
        tensorBackends={
            "pytorch": pytorch_result["pytorch_available"],
            "paddle": paddle_result["paddle_available"],
            "onnx": onnx_result["onnx_available"],
        },
        tensorEngines=tensor_engines,
        backendDeviceSupport=backend_device_support,
        onnxRuntime={
            "available": onnx_result["onnx_available"],
            "providers": onnx_result["providers"],
        },
        rifeModel={
            "available": default_model_available,
            "version": settings.RIFE_MODEL_VERSION,
            "path": str(default_model_path),
        },
        interpolationAlgorithms=interpolation_algorithms_payload,
        superResolutionAlgorithms=super_resolution_algorithms_payload,
        animeProfiles=ANIME_PROFILES,
        runtime={
            "mode": settings.runtime_mode,
            "bundled": settings.bundled_runtime_available,
            "pythonExecutable": settings.PYTHON_EXECUTABLE,
            "defaultModelAvailable": default_model_available,
        },
        resources=settings.resource_summary(),
    )
