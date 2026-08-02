"""Generated from contracts/application-defaults.json. Do not edit."""

from types import MappingProxyType
from typing import Final

DEFAULT_RIFE_ALGORITHM: Final = "rife"
DEFAULT_RIFE_MODEL_VERSION: Final = "4.25"
DEFAULT_RIFE_ONNX_MODEL: Final = ""
DEFAULT_RIFE_TARGET_FPS: Final = 60
DEFAULT_RIFE_MULTI: Final = 2
DEFAULT_RIFE_SCALE: Final = 1
DEFAULT_RIFE_FP16: Final = False
DEFAULT_RIFE_TENSOR_BACKEND: Final = "pytorch"
DEFAULT_RIFE_ENGINE: Final = "cuda"
DEFAULT_SR_ALGORITHM: Final = "placeholder"
DEFAULT_SR_ONNX_MODEL: Final = ""
DEFAULT_SR_SCALE_FACTOR: Final = 2
DEFAULT_SR_NUM_FRAMES: Final = 10
DEFAULT_SR_TENSOR_BACKEND: Final = "onnx"
DEFAULT_SR_ENGINE: Final = "cuda"
DEFAULT_CLI_FPS_MODE: Final = "multi"
DEFAULT_PROCESS_ORDER: Final = "super_resolution_then_interpolation"
DEFAULT_SEGMENT_FRAMES: Final = 1000
# fmt: off
FILTER_DEFAULTS: Final = MappingProxyType({"scale": MappingProxyType({"mode": "factor", "factor": 0.5, "width": 1920, "height": 1080, "interpolation": "lanczos4"}), "crop": MappingProxyType({"x": 0, "y": 0, "width": 1920, "height": 1080}), "pad": MappingProxyType({"top": 0, "bottom": 0, "left": 0, "right": 0, "color": "#000000"}), "sharpen": MappingProxyType({"amount": 0.5}), "denoise": MappingProxyType({"strength": 10, "colorStrength": 10}), "color": MappingProxyType({"brightness": 0, "contrast": 1, "saturation": 1}), "animeCleanup": MappingProxyType({"defaultProfile": "clean-lines", "profiles": MappingProxyType({"clean-lines": MappingProxyType({"denoise": 15, "edgeBoost": 30}), "thin-outline": MappingProxyType({"denoise": 8, "edgeBoost": 45}), "balanced-cel": MappingProxyType({"denoise": 25, "edgeBoost": 20})})})})
# fmt: on
