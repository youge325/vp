from pathlib import Path

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
        def __init__(self, *, model_id: str, num_frames: int, engine: str):
            created.append((model_id, num_frames, engine))

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
        engine="tensorrt",
        auto_download_weights=True,
    )

    assert algorithm.validate()
    assert algorithm.needs_frame_sequence()
    progress_calls = []
    output = algorithm.process_frame_sequence(
        frames,
        progress_callback=lambda current, total: progress_calls.append((current, total)),
    )

    assert created == [("ppmsvsr", 6, "tensorrt")]
    assert progress_calls == [(2, 2)]
    assert np.array_equal(output[0], frames[0] + 2)
    assert np.array_equal(output[1], frames[1] + 2)


def test_paddlegan_recurrent_runner_reports_completed_frames_by_chunk(monkeypatch):
    frames = [np.full((1, 1, 3), index, dtype=np.uint8) for index in range(5)]
    runner = PaddleGanVsrRunner(model_id="ppmsvsr", num_frames=2)
    runner._ensure_paddle = lambda: _NoGradPaddle()
    runner._ensure_model = lambda: lambda tensor: tensor
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
    runner._ensure_model = lambda: lambda _tensor: "frame"
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


def test_configure_tensorrt_predictor_enables_gpu_trt_and_shape():
    from app.algorithms.paddle.paddlegan_vsr.runner import _configure_tensorrt_config

    calls = []

    class _PrecisionType:
        Float32 = "float32"

    class _Inference:
        PrecisionType = _PrecisionType

    class _Paddle:
        inference = _Inference

    class _Config:
        def enable_use_gpu(self, memory_pool_init_size_mb, device_id):
            calls.append(("enable_use_gpu", memory_pool_init_size_mb, device_id))

        def switch_ir_optim(self, value):
            calls.append(("switch_ir_optim", value))

        def set_optim_cache_dir(self, cache_dir):
            calls.append(("set_optim_cache_dir", cache_dir))

        def enable_tensorrt_engine(self, **kwargs):
            calls.append(("enable_tensorrt_engine", kwargs))

        def set_trt_dynamic_shape_info(self, min_shape, max_shape, optim_shape):
            calls.append(("set_trt_dynamic_shape_info", min_shape, max_shape, optim_shape))

        def enable_tensorrt_memory_optim(self):
            calls.append(("enable_tensorrt_memory_optim",))

        def tensorrt_engine_enabled(self):
            return True

    _configure_tensorrt_config(
        _Config(),
        _Paddle(),
        input_name="input",
        min_shape=[1, 5, 3, 128, 128],
        max_shape=[1, 5, 3, 128, 128],
        optim_shape=[1, 5, 3, 128, 128],
        cache_dir="cache-dir",
    )

    assert calls[0] == ("enable_use_gpu", 512, 0)
    assert calls[1] == ("switch_ir_optim", True)
    assert calls[2] == ("set_optim_cache_dir", "cache-dir")
    assert calls[3][0] == "enable_tensorrt_engine"
    assert calls[3][1]["precision_mode"] == "float32"
    assert calls[3][1]["use_static"] is True
    assert calls[3][1]["use_calib_mode"] is False
    assert calls[4] == (
        "set_trt_dynamic_shape_info",
        {"input": [1, 5, 3, 128, 128]},
        {"input": [1, 5, 3, 128, 128]},
        {"input": [1, 5, 3, 128, 128]},
    )
    assert calls[5] == ("enable_tensorrt_memory_optim",)


def test_paddlegan_tensorrt_predictor_pads_and_crops_short_chunks(monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr.runner import _PaddleGanTensorRtPredictor

    copied_inputs = []

    class _InputHandle:
        def copy_from_cpu(self, array):
            copied_inputs.append(array.copy())

    class _OutputHandle:
        def copy_to_cpu(self):
            return np.zeros((1, 5, 3, 512, 512), dtype=np.float32)

    class _Predictor:
        def get_input_handle(self, _name):
            return _InputHandle()

        def run(self):
            return None

        def get_output_handle(self, name):
            assert name == "final"
            return _OutputHandle()

    predictor = _PaddleGanTensorRtPredictor(
        paddle=object(),
        model=object(),
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    monkeypatch.setattr(predictor, "_ensure_predictor", lambda _shape: (_Predictor(), "input", ["aux", "final"]))

    output = predictor.run(np.zeros((1, 3, 3, 128, 128), dtype=np.float32))

    assert copied_inputs[0].shape == (1, 5, 3, 128, 128)
    assert output.shape == (1, 3, 3, 512, 512)


def test_paddlegan_tensorrt_predictor_logs_build_save_cache_and_ready(tmp_path, monkeypatch, capsys):
    from app.algorithms.paddle.paddlegan_vsr.runner import _PaddleGanTensorRtPredictor

    saved_prefixes = []
    prefix = tmp_path / "ppmsvsr" / "t5_h288_w640" / "model"

    class _InputSpec:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _Static:
        InputSpec = _InputSpec

    class _Jit:
        def to_static(self, model, *, input_spec, full_graph):
            assert model == "model"
            assert input_spec[0].kwargs["shape"] == [1, 5, 3, 288, 640]
            assert full_graph is True
            return "static-model"

        def save(self, static_model, save_prefix):
            assert static_model == "static-model"
            saved_prefixes.append(save_prefix)
            Path(save_prefix).parent.mkdir(parents=True, exist_ok=True)
            Path(f"{save_prefix}.json").write_text("model", encoding="utf-8")
            Path(f"{save_prefix}.pdiparams").write_text("params", encoding="utf-8")

    class _Paddle:
        static = _Static()
        jit = _Jit()

    predictor = _PaddleGanTensorRtPredictor(
        paddle=_Paddle(),
        model="model",
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    monkeypatch.setattr(
        runner_module,
        "_tensorrt_model_prefix",
        lambda model_id, max_frames, height, width: prefix,
    )
    monkeypatch.setattr(
        runner_module,
        "_create_tensorrt_predictor",
        lambda **_kwargs: ("predictor", "input", ["output"]),
    )

    predictor._ensure_predictor([1, 5, 3, 288, 640])

    stderr = capsys.readouterr().err
    assert saved_prefixes == [str(prefix)]
    assert "[VP_TRT] BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640" in stderr
    assert "[VP_TRT] SAVE static_model=" in stderr
    assert "[VP_TRT] CACHE dir=" in stderr
    assert "[VP_TRT] READY outputs=output" in stderr


def test_paddlegan_tensorrt_predictor_logs_load_when_static_files_exist(tmp_path, monkeypatch, capsys):
    from app.algorithms.paddle.paddlegan_vsr.runner import _PaddleGanTensorRtPredictor

    prefix = tmp_path / "ppmsvsr" / "t5_h288_w640" / "model"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{prefix}.json").write_text("model", encoding="utf-8")
    Path(f"{prefix}.pdiparams").write_text("params", encoding="utf-8")

    class _Jit:
        def save(self, *_args, **_kwargs):
            raise AssertionError("cached TensorRT static files should not be saved again")

    class _Paddle:
        jit = _Jit()

    predictor = _PaddleGanTensorRtPredictor(
        paddle=_Paddle(),
        model="model",
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    monkeypatch.setattr(
        runner_module,
        "_tensorrt_model_prefix",
        lambda model_id, max_frames, height, width: prefix,
    )
    monkeypatch.setattr(
        runner_module,
        "_create_tensorrt_predictor",
        lambda **_kwargs: ("predictor", "input", ["output"]),
    )

    predictor._ensure_predictor([1, 5, 3, 288, 640])

    stderr = capsys.readouterr().err
    assert "[VP_TRT] LOAD static_model=" in stderr
    assert "[VP_TRT] CACHE dir=" in stderr
    assert "[VP_TRT] READY outputs=output" in stderr
    assert "[VP_TRT] BUILD" not in stderr


def test_paddlegan_tensorrt_predictor_logs_in_process_reuse(capsys):
    from app.algorithms.paddle.paddlegan_vsr.runner import _PaddleGanTensorRtPredictor

    predictor = _PaddleGanTensorRtPredictor(
        paddle=object(),
        model=object(),
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    predictor._cache[(5, 288, 640)] = ("predictor", "input", ["output"])

    assert predictor._ensure_predictor([1, 5, 3, 288, 640]) == ("predictor", "input", ["output"])
    assert predictor._ensure_predictor([1, 5, 3, 288, 640]) == ("predictor", "input", ["output"])

    stderr = capsys.readouterr().err
    assert stderr.count("[VP_TRT] REUSE PaddleGAN ppmsvsr shape=1x5x3x288x640") == 1
