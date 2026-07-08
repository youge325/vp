from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.planning import ProcessingStep
from app.processing.streaming import stage_worker_factory


class _Backend:
    def get_name(self) -> str:
        return "identity"


def test_stage_worker_factory_skips_backend_for_frame_filter_chain() -> None:
    config = SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="frame_filter_chain",
            algorithm_kwargs={},
            stage_name="01_frame_filter_chain",
        ),
        tensor_backend_name="pytorch",
    )
    calls: list[str] = []

    assert stage_worker_factory.create_backend(config, lambda name: calls.append(name)) is None
    assert calls == []


def test_stage_worker_factory_passes_filtered_kwargs_to_algorithm_factory(monkeypatch) -> None:
    captured = {}

    def fake_create(*, algorithm_type, tensor_backend, tensor_backend_name, **kwargs):
        captured.update(
            {
                "algorithm_type": algorithm_type,
                "tensor_backend": tensor_backend,
                "tensor_backend_name": tensor_backend_name,
                "kwargs": kwargs,
            }
        )
        return "algorithm"

    monkeypatch.setattr(stage_worker_factory.AlgorithmFactory, "create", staticmethod(fake_create))
    monkeypatch.setattr(stage_worker_factory, "register_single_algorithm", lambda _algorithm_type: None)
    stage = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"sr_algorithm": "ppmsvsr", "tensor_backend": "paddle", "num_frames": 5},
        stage_name="01_super_resolution",
    )

    assert stage_worker_factory.create_algorithm(stage, _Backend()) == "algorithm"
    assert captured == {
        "algorithm_type": "super_resolution",
        "tensor_backend": captured["tensor_backend"],
        "tensor_backend_name": "identity",
        "kwargs": {"sr_algorithm": "ppmsvsr", "num_frames": 5},
    }
    assert captured["tensor_backend"].get_name() == "identity"


def test_stage_worker_factory_rejects_unknown_algorithm_type() -> None:
    with pytest.raises(ValueError, match="Unsupported stage-worker algorithm type"):
        stage_worker_factory.register_single_algorithm("unknown")
