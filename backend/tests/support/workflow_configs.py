from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_WORKFLOW_CONFIG: dict[str, Any] = {
    "fpsMode": "target",
    "processOrder": "super_resolution_then_interpolation",
    "interpolation": {
        "enabled": True,
        "targetFps": 60,
        "multi": 2,
        "algorithm": "rife",
        "model": "4.25",
        "onnxModel": None,
        "scale": 1.0,
        "fp16": False,
        "tensorBackend": "pytorch",
        "engine": "cuda",
    },
    "superResolution": {
        "enabled": False,
        "scaleFactor": 2.0,
        "algorithm": "placeholder",
        "onnxModel": None,
        "tensorBackend": "onnx",
        "engine": "cuda",
        "numFrames": 10,
    },
    "preprocess": {"enabled": False, "filters": []},
    "postprocess": {"enabled": False, "filters": []},
}


def make_workflow_config(**overrides: Any) -> dict[str, Any]:
    workflow = deepcopy(_BASE_WORKFLOW_CONFIG)
    for key, value in overrides.items():
        current = workflow.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            current.update(value)
        else:
            workflow[key] = value
    return workflow
