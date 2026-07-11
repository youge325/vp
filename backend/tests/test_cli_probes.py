from __future__ import annotations

from typing import Any

from app.cli import probes


def test_probe_tensor_engines_maps_available_capabilities(monkeypatch) -> None:
    results = iter(
        [
            {"pytorch_available": True, "supports_cuda": True, "supports_tensorrt": False},
            {
                "paddle_available": True,
                "supports_cuda": True,
                "supports_tensorrt": True,
                "supports_dcu": False,
            },
            {"onnx_available": True, "supports_cuda": True, "supports_tensorrt": True},
        ]
    )

    def fake_probe(_script: str, _fallback: dict[str, Any]) -> dict[str, Any]:
        return next(results)

    monkeypatch.setattr(probes, "_run_python_capability_probe", fake_probe)

    assert probes.probe_tensor_engines() == {
        "pytorch": ["cuda"],
        "paddle": ["cuda", "tensorrt"],
        "onnx": ["tensorrt", "cuda"],
    }


def test_probe_tensor_engines_hides_engines_when_runtime_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        probes,
        "_run_python_capability_probe",
        lambda _script, _fallback: {
            "pytorch_available": False,
            "paddle_available": False,
            "onnx_available": False,
            "supports_cuda": True,
            "supports_tensorrt": True,
            "supports_dcu": True,
        },
    )

    assert probes.probe_tensor_engines() == {"pytorch": [], "paddle": [], "onnx": []}
