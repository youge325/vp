// Generated from contracts/application-defaults.json. Do not edit.
export const APPLICATION_DEFAULTS = {
  "interpolation": {
    "algorithm": "rife",
    "model": "4.25",
    "onnxModel": "",
    "targetFps": 60,
    "multi": 2,
    "scale": 1,
    "fp16": false,
    "tensorBackend": "pytorch",
    "engine": "cuda"
  },
  "superResolution": {
    "algorithm": "placeholder",
    "onnxModel": "",
    "scaleFactor": 2,
    "numFrames": 10,
    "tensorBackend": "onnx",
    "engine": "cuda"
  },
  "workflow": {
    "desktopFpsMode": "target",
    "cliFpsMode": "multi",
    "processOrder": "super_resolution_then_interpolation"
  },
  "output": {
    "segmentFrames": 1000
  }
} as const
