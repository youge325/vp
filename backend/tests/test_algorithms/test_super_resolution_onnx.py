import sys
from pathlib import Path

import numpy as np

from app.processing.super_resolution import SuperResolutionAlgorithm


class _OnnxBackend:
    def get_name(self) -> str:
        return "onnx"


class _Node:
    def __init__(self, name: str):
        self.name = name


def test_super_resolution_onnx_lazily_loads_and_scales(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "super_resolution" / "placeholder"
    model_dir.mkdir(parents=True)
    (model_dir / "sr.onnx").write_bytes(b"model")
    created_sessions = []

    class _Session:
        def __init__(self, path: str, providers):
            created_sessions.append((path, providers))
            self._providers = list(providers)

        def get_providers(self):
            return list(self._providers)

        def get_inputs(self):
            return [_Node("input")]

        def get_outputs(self):
            return [_Node("output")]

        def run(self, _outputs, feed):
            tensor = feed["input"]
            return [np.repeat(np.repeat(tensor, 2, axis=2), 2, axis=3)]

    class _Ort:
        @staticmethod
        def get_available_providers():
            return ["CPUExecutionProvider"]

        InferenceSession = _Session

    monkeypatch.setitem(sys.modules, "onnxruntime", _Ort)
    algorithm = SuperResolutionAlgorithm(
        tensor_backend=_OnnxBackend(),
        scale_factor=2,
        onnx_model="sr.onnx",
        model_dir=str(tmp_path),
        engine="auto",
    )

    assert created_sessions == []
    output = algorithm.process_frame(np.ones((1, 3, 2, 3), dtype=np.float32))

    assert output.shape == (1, 3, 4, 6)
    assert len(created_sessions) == 1
    assert Path(created_sessions[0][0]).name == "sr.onnx"
