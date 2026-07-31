from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.planning.processing_steps import ProcessingStep
from app.processing.streaming import stage_worker_factory


class _Backend:
    pass


def test_stage_worker_factory_skips_backend_for_frame_filter_chain(monkeypatch) -> None:
    config = SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="frame_filter_chain",
            algorithm_kwargs={},
            stage_name="01_frame_filter_chain",
        ),
        tensor_backend_name=None,
    )
    calls: list[str] = []
    monkeypatch.setattr(stage_worker_factory, "get_tensor_backend", lambda name: calls.append(name))

    assert stage_worker_factory.create_backend(config, config.stage) is None
    assert calls == []


def test_stage_worker_factory_skips_backend_for_sequence_stages(monkeypatch) -> None:
    config = SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        tensor_backend_name="paddle",
    )
    monkeypatch.setattr(stage_worker_factory, "get_tensor_backend", lambda name: {"backend": name})

    assert stage_worker_factory.create_backend(config, config.stage) is None


def test_stage_worker_factory_passes_filtered_kwargs_to_algorithm(monkeypatch) -> None:
    from app.algorithms import onnx_super_resolution

    captured = {}

    class FakeAlgorithm:
        def __init__(self, **kwargs):
            captured.update({"kwargs": kwargs})

    monkeypatch.setattr(onnx_super_resolution, "OnnxSuperResolution", FakeAlgorithm)
    stage = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "sr_algorithm": "placeholder",
            "tensor_backend": "onnx",
            "scale_factor": 2.0,
            "onnx_model": "sr.onnx",
            "engine": "cuda",
        },
        stage_name="01_super_resolution",
    )

    algorithm = stage_worker_factory.create_algorithm(stage, _Backend(), model_root="D:/models")

    assert isinstance(algorithm, FakeAlgorithm)
    assert captured["kwargs"] == {
        "sr_algorithm": "placeholder",
        "onnx_model": "sr.onnx",
        "engine": "cuda",
        "model_dir": "D:/models",
    }


def test_stage_worker_factory_accepts_immutable_filter_params() -> None:
    stage = ProcessingStep(
        algorithm_type="frame_filter_chain",
        algorithm_kwargs={
            "filters": [
                {
                    "kind": "anime_cleanup",
                    "enabled": True,
                    "params": {"profile": "clean-lines", "denoise": 0, "edgeBoost": 0},
                }
            ]
        },
        stage_name="01_preprocess",
    )
    frame = np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3)

    algorithm = stage_worker_factory.create_algorithm(stage, None, model_root="D:/models")

    assert algorithm.process_numpy(frame) is frame


def test_stage_worker_factory_rejects_unknown_algorithm_type() -> None:
    with pytest.raises(ValueError, match="Unknown processing stage type"):
        stage_worker_factory.create_algorithm(
            ProcessingStep(
                algorithm_type="unknown",
                algorithm_kwargs={},
                stage_name="01_unknown",
            ),
            _Backend(),
            model_root="D:/models",
        )
