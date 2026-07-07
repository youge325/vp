import importlib.util
import sys
import types

import pytest

pytestmark = pytest.mark.pytorch


def test_pytorch_rife_tensorrt_requires_torch_tensorrt(monkeypatch):
    import torch.nn as nn

    from app.algorithms.pytorch.rife import model_loader

    original_find_spec = importlib.util.find_spec

    def find_spec(name: str, *args, **kwargs):
        if name == "torch_tensorrt":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(model_loader.importlib.util, "find_spec", find_spec)

    with pytest.raises(RuntimeError, match="torch_tensorrt"):
        model_loader._compile_with_tensorrt_if_available(nn.Identity(), label="unit-test", fp16=False)


def test_pytorch_rife_tensorrt_requires_strict_compile(monkeypatch):
    import torch
    import torch.nn as nn

    from app.algorithms.pytorch.rife import model_loader

    fake_torch_tensorrt = types.ModuleType("torch_tensorrt")
    fake_torch_tensorrt.__spec__ = importlib.util.spec_from_loader("torch_tensorrt", loader=None)
    monkeypatch.setitem(sys.modules, "torch_tensorrt", fake_torch_tensorrt)
    monkeypatch.setattr(
        model_loader.importlib.util, "find_spec", lambda name: object() if name == "torch_tensorrt" else None
    )
    captured = {}

    def compile_module(module, *, backend, options):
        captured["backend"] = backend
        captured["options"] = options
        return module

    monkeypatch.setattr(torch, "compile", compile_module)

    module = nn.Identity()
    assert model_loader._compile_with_tensorrt_if_available(module, label="unit-test", fp16=False) is module
    assert captured["backend"] == "tensorrt"
    assert captured["options"]["require_full_compilation"] is True
    assert captured["options"]["pass_through_build_failures"] is True
