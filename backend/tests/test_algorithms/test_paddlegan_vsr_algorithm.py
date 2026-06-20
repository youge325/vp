import numpy as np

from app.processing.super_resolution import SUPPORTED_ALGORITHMS, SuperResolutionAlgorithm


class _PaddleBackend:
    def get_name(self) -> str:
        return "paddle"


def test_supported_super_resolution_algorithms_include_all_paddlegan_vsr_models():
    algorithms = {entry["name"]: entry for entry in SUPPORTED_ALGORITHMS}

    for name in ["ppmsvsr", "ppmsvsr-large", "edvr", "basicvsr", "iconvsr", "basicvsr-plus-plus"]:
        assert algorithms[name]["tensorBackends"] == ["paddle"]
        assert algorithms[name]["models"] == ["x4"]
        assert algorithms[name]["scaleFactors"] == [4]


def test_paddlegan_super_resolution_delegates_to_sequence_runner(monkeypatch):
    frames = [np.zeros((2, 2, 3), dtype=np.uint8), np.ones((2, 2, 3), dtype=np.uint8)]
    created = []

    class _Runner:
        def __init__(self, *, model_id: str, num_frames: int, auto_download_weights: bool):
            created.append((model_id, num_frames, auto_download_weights))

        def process_frames(self, input_frames):
            assert input_frames == frames
            return [frame + 2 for frame in input_frames]

    monkeypatch.setattr("app.processing.super_resolution.PaddleGanVsrRunner", _Runner)

    algorithm = SuperResolutionAlgorithm(
        tensor_backend=_PaddleBackend(),
        sr_algorithm="ppmsvsr",
        scale_factor=4,
        num_frames=6,
        auto_download_weights=False,
    )

    assert algorithm.validate()
    assert algorithm.needs_frame_sequence()
    output = algorithm.process_frame_sequence(frames)

    assert created == [("ppmsvsr", 6, False)]
    assert np.array_equal(output[0], frames[0] + 2)
    assert np.array_equal(output[1], frames[1] + 2)
