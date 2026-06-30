"""Configuration edge cases for the RIFE model loader."""

from __future__ import annotations

import types

import pytest


class _FakeCuda:
    @staticmethod
    def is_available() -> bool:
        return False


class _FakeTorch(types.SimpleNamespace):
    cuda = _FakeCuda()
    half = object()
    float = object()

    @staticmethod
    def device(value: str) -> str:
        return value


def test_default_model_dir_uses_settings_rife_model_dir(monkeypatch, tmp_path) -> None:
    from app.algorithms.pytorch.rife.model_loader import get_model_dir
    from app.config import settings

    model_root = tmp_path / "configured-models"
    monkeypatch.delenv("VP_RIFE_MODEL_DIR", raising=False)
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(model_root))

    assert get_model_dir() == str(model_root)
    assert model_root.is_dir()


def test_empty_model_dir_uses_vp_rife_model_dir(monkeypatch, tmp_path) -> None:
    """CLI-created algorithms pass empty model_dir today; it must still use env config."""
    from app.algorithms.pytorch.rife.model_loader import load_rife_model

    model_root = tmp_path / "models"
    model_root.mkdir()
    monkeypatch.setenv("VP_RIFE_MODEL_DIR", str(model_root))
    monkeypatch.setitem(__import__("sys").modules, "torch", _FakeTorch())

    with pytest.raises(FileNotFoundError) as exc_info:
        load_rife_model(model_version="4.25", model_dir="")

    assert str(model_root / "flownet_v4.25.pkl") in str(exc_info.value)
