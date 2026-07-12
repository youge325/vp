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


def test_stage_worker_factory_uses_backend_factory_for_tensor_stages() -> None:
    config = SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        tensor_backend_name="paddle",
    )

    assert stage_worker_factory.create_backend(config, lambda name: {"backend": name}) == {"backend": "paddle"}


def test_stage_worker_factory_passes_filtered_kwargs_to_algorithm(monkeypatch) -> None:
    from app.processing import super_resolution

    captured = {}

    class FakeAlgorithm:
        def __init__(self, *, tensor_backend, **kwargs):
            captured.update({"tensor_backend": tensor_backend, "kwargs": kwargs})

    monkeypatch.setattr(super_resolution, "SuperResolutionAlgorithm", FakeAlgorithm)
    stage = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"sr_algorithm": "placeholder", "tensor_backend": "pytorch", "scale_factor": 2.0},
        stage_name="01_super_resolution",
    )

    algorithm = stage_worker_factory.create_algorithm(stage, _Backend())

    assert isinstance(algorithm, FakeAlgorithm)
    assert captured["kwargs"] == {"sr_algorithm": "placeholder", "scale_factor": 2.0}
    assert captured["tensor_backend"].get_name() == "identity"


def test_stage_worker_factory_rejects_unknown_algorithm_type() -> None:
    with pytest.raises(ValueError, match="Unsupported stage-worker algorithm type"):
        stage_worker_factory.create_algorithm(
            ProcessingStep(
                algorithm_type="unknown",
                algorithm_kwargs={},
                stage_name="01_unknown",
            ),
            _Backend(),
        )
