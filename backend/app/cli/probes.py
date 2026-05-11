"""Subprocess probes for tensor backends.

Each probe spawns ``python -c <script>`` in a child process to discover
runtime capabilities without polluting the current interpreter with
heavy GPU framework imports (PyTorch, Paddle, ONNX Runtime).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from app.config import settings
from app.utils.subprocess_utils import hidden_subprocess_kwargs


def _check_pytorch_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'pytorch_available': False, 'gpu_available': False, 'gpu_devices': [], "
        "          'supports_cuda': False, 'supports_tensorrt': False}\n"
        "try:\n"
        "    import torch\n"
        "    result['pytorch_available'] = True\n"
        "    if torch.cuda.is_available():\n"
        "        result['gpu_available'] = True\n"
        "        result['gpu_devices'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]\n"
        "        result['supports_cuda'] = True\n"
        "        result['supports_tensorrt'] = True\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {
        "pytorch_available": False,
        "gpu_available": False,
        "gpu_devices": [],
        "supports_cuda": False,
        "supports_tensorrt": False,
    }


def _check_paddle_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'paddle_available': False, 'supports_cuda': False, "
        "          'supports_tensorrt': False, 'supports_dcu': False}\n"
        "try:\n"
        "    import paddle\n"
        "    result['paddle_available'] = True\n"
        "    if paddle.device.is_compiled_with_cuda():\n"
        "        result['supports_cuda'] = True\n"
        "        result['supports_tensorrt'] = True\n"
        "    if paddle.device.is_compiled_with_rocm():\n"
        "        result['supports_dcu'] = True\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"paddle_available": False, "supports_cuda": False, "supports_tensorrt": False, "supports_dcu": False}


def _check_onnxruntime_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'onnx_available': False, 'providers': [], "
        "          'supports_cuda': False, 'supports_tensorrt': False}\n"
        "try:\n"
        "    import onnxruntime as ort\n"
        "    result['onnx_available'] = True\n"
        "    providers = ort.get_available_providers()\n"
        "    result['providers'] = providers\n"
        "    result['supports_cuda'] = 'CUDAExecutionProvider' in providers\n"
        "    # 有 CUDA provider 说明是 NVIDIA GPU，默认同时支持 TensorRT\n"
        "    result['supports_tensorrt'] = 'TensorrtExecutionProvider' in providers or 'CUDAExecutionProvider' in providers\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"onnx_available": False, "providers": [], "supports_cuda": False, "supports_tensorrt": False}
