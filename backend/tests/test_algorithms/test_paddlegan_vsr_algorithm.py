import logging
from pathlib import Path

import numpy as np
import pytest

from app.algorithms.paddle.paddlegan_vsr import sequence_executor as executor_module
from app.algorithms.paddle.paddlegan_vsr import tensor_codec
from app.algorithms.paddle.paddlegan_vsr import tensorrt_cache as tensorrt_module
from app.algorithms.paddle.paddlegan_vsr import trace_observer as trace_module
from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner
from app.algorithms.paddle.paddlegan_vsr.tensorrt_cache import (
    PaddleGanTensorRtPredictor,
    _PredictorBinding,
    _TensorRtPredictorCache,
)
from app.algorithms.paddle.paddlegan_vsr.trace_observer import PaddleGanTraceObserver
from app.algorithms.paddle_video_super_resolution import PaddleGanVideoSuperResolution
from app.catalog.algorithm_capabilities import SUPER_RESOLUTION_CAPABILITIES


class _NoGradPaddle:
    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_exc):
            return False

    def no_grad(self):
        return self._NoGrad()


def test_supported_super_resolution_algorithms_include_all_paddlegan_vsr_models():
    algorithms = {entry.name: entry for entry in SUPER_RESOLUTION_CAPABILITIES}

    for name in ["ppmsvsr", "ppmsvsr-large", "edvr", "basicvsr", "iconvsr", "basicvsr-plus-plus"]:
        assert algorithms[name].descriptor.supported_backends == frozenset({"paddle"})
        assert algorithms[name].models == ("x4",)
        assert algorithms[name].descriptor.fixed_scale_factor == 4


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"model_id": "ppmsvsr", "num_frames": 0, "engine": "cuda"}, "num_frames must be at least 1"),
        ({"model_id": "ppmsvsr", "num_frames": 5, "engine": "openvino"}, "Unsupported PaddleGAN VSR engine"),
    ],
)
def test_paddlegan_runner_rejects_invalid_runtime_parameters(kwargs, message):
    with pytest.raises(ValueError, match=message):
        PaddleGanVsrRunner(**kwargs)


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

    monkeypatch.setattr("app.algorithms.paddle_video_super_resolution.PaddleGanVsrRunner", _Runner)

    algorithm = PaddleGanVideoSuperResolution(
        sr_algorithm="ppmsvsr",
        num_frames=6,
        engine="tensorrt",
    )

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
    runner = PaddleGanVsrRunner(model_id="ppmsvsr", num_frames=2, engine="cuda")
    runner._ensure_paddle = lambda: _NoGradPaddle()
    runner._ensure_model = lambda: lambda tensor: tensor
    monkeypatch.setattr(executor_module, "frames_to_tensor", lambda chunk, _paddle: len(chunk))
    monkeypatch.setattr(
        executor_module,
        "sequence_tensor_to_frames",
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
    runner = PaddleGanVsrRunner(model_id="edvr", num_frames=5, engine="cuda")
    runner._ensure_paddle = lambda: _NoGradPaddle()
    runner._ensure_model = lambda: lambda _tensor: "frame"
    monkeypatch.setattr(executor_module, "frames_to_tensor", lambda _neighbors, _paddle: "neighbors")
    monkeypatch.setattr(
        executor_module,
        "image_tensor_to_frames",
        lambda _tensor: [np.zeros((1, 1, 3), dtype=np.uint8)],
    )
    progress_calls = []

    output = runner.process_frames(
        frames,
        progress_callback=lambda current, total: progress_calls.append((current, total)),
    )

    assert len(output) == 3
    assert progress_calls == [(1, 3), (2, 3), (3, 3)]


def test_paddlegan_tensor_outputs_share_rgb_uint8_conversion() -> None:
    chw = np.array([[[0.0]], [[0.5]], [[1.0]]], dtype=np.float32)
    sequence = np.stack([chw, chw * 0.5], axis=0)[np.newaxis, ...]
    images = np.stack([chw, chw * 0.5], axis=0)

    sequence_frames = tensor_codec.sequence_tensor_to_frames(sequence)
    image_frames = tensor_codec.image_tensor_to_frames(images)

    assert len(sequence_frames) == 2
    assert len(image_frames) == 2
    np.testing.assert_array_equal(sequence_frames[0], np.array([[[0, 128, 255]]], dtype=np.uint8))
    np.testing.assert_array_equal(image_frames[0], sequence_frames[0])
    np.testing.assert_array_equal(image_frames[1], sequence_frames[1])


@pytest.mark.parametrize(
    ("converter", "tensor", "message"),
    [
        (
            tensor_codec.sequence_tensor_to_frames,
            np.zeros((1, 3, 2, 2), dtype=np.float32),
            "PaddleGAN recurrent VSR output must be 5D",
        ),
        (
            tensor_codec.image_tensor_to_frames,
            np.zeros((1, 1, 3, 2, 2), dtype=np.float32),
            "PaddleGAN EDVR output must be 4D",
        ),
    ],
)
def test_paddlegan_tensor_outputs_reject_wrong_dimensions(converter, tensor, message) -> None:
    with pytest.raises(RuntimeError, match=message):
        converter(tensor)


def test_paddlegan_chunk_trace_records_shared_shape_payload(monkeypatch):
    trace_chunks = []
    sync_calls = []
    monkeypatch.setattr(trace_module, "_sync_paddle", lambda paddle: sync_calls.append(paddle))

    tensor = np.zeros((1, 2, 3, 4, 5), dtype=np.float32)
    output = np.zeros((1, 2, 3, 16, 20), dtype=np.float32)
    observer = PaddleGanTraceObserver(Path("trace.json"))
    observer._chunks = trace_chunks
    observer.record_chunk(
        "paddle",
        tensor=tensor,
        output=output,
        frame_count=2,
    )

    assert sync_calls == ["paddle"]
    assert trace_chunks == [
        {
            "chunkFrameCount": 2,
            "inputShape": [1, 2, 3, 4, 5],
            "outputShape": [1, 2, 3, 16, 20],
        }
    ]


def test_configure_tensorrt_predictor_enables_gpu_trt_and_shape():
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

    tensorrt_module._configure_tensorrt_config(
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

    predictor = PaddleGanTensorRtPredictor(
        paddle=object(),
        model=object(),
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    monkeypatch.setattr(
        predictor._cache,
        "ensure",
        lambda _shape: _PredictorBinding(_Predictor(), "input", ["aux", "final"]),
    )

    output = predictor.run(np.zeros((1, 3, 3, 128, 128), dtype=np.float32))

    assert copied_inputs[0].shape == (1, 5, 3, 128, 128)
    assert output.shape == (1, 3, 3, 512, 512)


def _ensure_tensorrt_predictor(monkeypatch, caplog, *, prefix: Path, paddle):
    caplog.set_level(logging.INFO, logger=tensorrt_module.__name__)
    cache = _TensorRtPredictorCache(
        paddle=paddle,
        model="model",
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    monkeypatch.setattr(tensorrt_module, "_tensorrt_model_prefix", lambda *_args, **_kwargs: prefix)
    monkeypatch.setattr(
        tensorrt_module,
        "_create_tensorrt_predictor",
        lambda **_kwargs: _PredictorBinding("predictor", "input", ["output"]),
    )
    cache.ensure([1, 5, 3, 288, 640])
    return [record.getMessage() for record in caplog.records if record.name == tensorrt_module.__name__]


def test_paddlegan_tensorrt_predictor_logs_build_save_cache_and_ready(tmp_path, monkeypatch, caplog):
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

    messages = _ensure_tensorrt_predictor(monkeypatch, caplog, prefix=prefix, paddle=_Paddle())
    assert saved_prefixes == [str(prefix)]
    assert "[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640" in messages
    assert any(message.startswith("[VP_TRT] TensorRT SAVE static_model=") for message in messages)
    assert any(message.startswith("[VP_TRT] TensorRT CACHE dir=") for message in messages)
    assert "[VP_TRT] TensorRT READY outputs=output" in messages


def test_paddlegan_tensorrt_predictor_logs_load_when_static_files_exist(tmp_path, monkeypatch, caplog):
    prefix = tmp_path / "ppmsvsr" / "t5_h288_w640" / "model"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{prefix}.json").write_text("model", encoding="utf-8")
    Path(f"{prefix}.pdiparams").write_text("params", encoding="utf-8")

    class _Jit:
        def save(self, *_args, **_kwargs):
            raise AssertionError("cached TensorRT static files should not be saved again")

    class _Paddle:
        jit = _Jit()

    messages = _ensure_tensorrt_predictor(monkeypatch, caplog, prefix=prefix, paddle=_Paddle())
    assert any(message.startswith("[VP_TRT] TensorRT LOAD static_model=") for message in messages)
    assert any(message.startswith("[VP_TRT] TensorRT CACHE dir=") for message in messages)
    assert "[VP_TRT] TensorRT READY outputs=output" in messages
    assert not any("[VP_TRT] TensorRT BUILD" in message for message in messages)


def test_paddlegan_tensorrt_predictor_logs_in_process_reuse(caplog):
    caplog.set_level(logging.INFO, logger=tensorrt_module.__name__)
    cache = _TensorRtPredictorCache(
        paddle=object(),
        model=object(),
        model_id="ppmsvsr",
        sequence_mode="recurrent",
        num_frames=5,
    )
    cache._entries[(5, 288, 640)] = _PredictorBinding("predictor", "input", ["output"])

    expected = _PredictorBinding("predictor", "input", ["output"])
    assert cache.ensure([1, 5, 3, 288, 640]) == expected
    assert cache.ensure([1, 5, 3, 288, 640]) == expected

    messages = [record.getMessage() for record in caplog.records if record.name == tensorrt_module.__name__]
    assert messages.count("[VP_TRT] TensorRT REUSE PaddleGAN ppmsvsr shape=1x5x3x288x640") == 1
