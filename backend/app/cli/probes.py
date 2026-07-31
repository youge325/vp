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
from app.catalog.tensor_capabilities import BACKEND_ENGINES
from app.generated.contracts import InferenceEngine, TensorEngines
from app.utils.subprocess_utils import hidden_subprocess_kwargs

_PYTORCH_SCRIPT = (
    "import json\n"
    "result = {'pytorch_available': False, 'supports_cuda': False, 'supports_tensorrt': False}\n"
    "try:\n"
    "    import torch\n"
    "    result['pytorch_available'] = True\n"
    "    if torch.cuda.is_available():\n"
    "        result['supports_cuda'] = True\n"
    "        result['supports_tensorrt'] = True\n"
    "except (ImportError, OSError):\n"
    "    pass\n"
    "print(json.dumps(result), flush=True)\n"
)

_PADDLE_SCRIPT = (
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

_ONNX_SCRIPT = (
    "import json\n"
    "result = {'onnx_available': False, 'supports_cuda': False, 'supports_tensorrt': False}\n"
    "try:\n"
    "    import onnxruntime as ort\n"
    "    result['onnx_available'] = True\n"
    "    providers = ort.get_available_providers()\n"
    "    result['supports_cuda'] = 'CUDAExecutionProvider' in providers\n"
    "    # 有 CUDA provider 说明是 NVIDIA GPU，默认同时支持 TensorRT\n"
    "    result['supports_tensorrt'] = 'TensorrtExecutionProvider' in providers or 'CUDAExecutionProvider' in providers\n"
    "except (ImportError, OSError):\n"
    "    pass\n"
    "print(json.dumps(result), flush=True)\n"
)

_PROBE_SPECS: dict[str, tuple[str, str]] = {
    "pytorch": (_PYTORCH_SCRIPT, "pytorch_available"),
    "paddle": (_PADDLE_SCRIPT, "paddle_available"),
    "onnx": (_ONNX_SCRIPT, "onnx_available"),
}


def _run_python_capability_probe(script: str, fallback: dict[str, Any]) -> dict[str, Any]:
    """Spawn a child interpreter to run *script* and parse the JSON it prints.

    Returns *fallback* (a fresh copy) on any failure mode: timeout, decode
    error, OS error, non-zero exit, or empty stdout. The probe is designed
    to never raise — capability detection is best-effort.
    """
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
    return dict(fallback)


def probe_tensor_engines() -> TensorEngines:
    """Probe each tensor runtime and return a validated wire model."""
    engines_by_backend: dict[str, list[str]] = {}
    for backend, (script, availability_key) in _PROBE_SPECS.items():
        engine_order = BACKEND_ENGINES[backend]
        fallback = {
            availability_key: False,
            **{f"supports_{engine}": False for engine in engine_order},
        }
        capabilities = _run_python_capability_probe(script, fallback)
        engines_by_backend[backend] = (
            [engine for engine in engine_order if capabilities.get(f"supports_{engine}")]
            if capabilities.get(availability_key)
            else []
        )
    return TensorEngines(
        pytorch=[InferenceEngine(engine) for engine in engines_by_backend["pytorch"]],
        paddle=[InferenceEngine(engine) for engine in engines_by_backend["paddle"]],
        onnx=[InferenceEngine(engine) for engine in engines_by_backend["onnx"]],
    )
