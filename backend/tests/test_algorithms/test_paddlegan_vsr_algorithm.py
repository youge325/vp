import numpy as np

from app.algorithms.paddle.paddlegan_vsr import runner as runner_module
from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner
from app.processing.super_resolution import SUPPORTED_ALGORITHMS, SuperResolutionAlgorithm


class _PaddleBackend:
    def get_name(self) -> str:
        return "paddle"


class _NoGradPaddle:
    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_exc):
            return False

    def no_grad(self):
        return self._NoGrad()


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
        def __init__(self, *, model_id: str, num_frames: int):
            created.append((model_id, num_frames))

        def process_frames(self, input_frames, *, progress_callback=None):
            assert input_frames == frames
            if progress_callback is not None:
                progress_callback(len(input_frames), len(input_frames))
            return [frame + 2 for frame in input_frames]

    monkeypatch.setattr("app.processing.super_resolution.PaddleGanVsrRunner", _Runner)

    algorithm = SuperResolutionAlgorithm(
        tensor_backend=_PaddleBackend(),
        sr_algorithm="ppmsvsr",
        scale_factor=4,
        num_frames=6,
        auto_download_weights=True,
    )

    assert algorithm.validate()
    assert algorithm.needs_frame_sequence()
    progress_calls = []
    output = algorithm.process_frame_sequence(
        frames,
        progress_callback=lambda current, total: progress_calls.append((current, total)),
    )

    assert created == [("ppmsvsr", 6)]
    assert progress_calls == [(2, 2)]
    assert np.array_equal(output[0], frames[0] + 2)
    assert np.array_equal(output[1], frames[1] + 2)


def test_paddlegan_recurrent_runner_reports_completed_frames_by_chunk(monkeypatch):
    frames = [np.full((1, 1, 3), index, dtype=np.uint8) for index in range(5)]
    runner = PaddleGanVsrRunner(model_id="ppmsvsr", num_frames=2)
    runner._ensure_paddle = lambda: _NoGradPaddle()
    runner._ensure_model = lambda: (lambda tensor: tensor)
    runner._frames_to_tensor = lambda chunk: len(chunk)
    monkeypatch.setattr(
        runner_module,
        "_sequence_tensor_to_frames",
        lambda count: [np.zeros((1, 1, 3), dtype=np.uint8) for _ in range(count)],
    )
    progress_calls = []

    output = runner.process_frames(
        frames,
        progress_callback=lambda current, total: progress_calls.append((current, total)),
    )

    assert len(output) == 5
    assert progress_calls == [(2, 5), (4, 5), (5, 5)]


def test_paddlegan_window_runner_reports_completed_frames_by_window(monkeypatch):
    frames = [np.full((1, 1, 3), index, dtype=np.uint8) for index in range(3)]
    runner = PaddleGanVsrRunner(model_id="edvr", num_frames=5)
    runner._ensure_paddle = lambda: _NoGradPaddle()
    runner._ensure_model = lambda: (lambda _tensor: "frame")
    runner._frames_to_tensor = lambda _neighbors: "neighbors"
    monkeypatch.setattr(
        runner_module,
        "_image_tensor_to_frames",
        lambda _tensor: [np.zeros((1, 1, 3), dtype=np.uint8)],
    )
    progress_calls = []

    output = runner.process_frames(
        frames,
        progress_callback=lambda current, total: progress_calls.append((current, total)),
    )

    assert len(output) == 3
    assert progress_calls == [(1, 3), (2, 3), (3, 3)]
