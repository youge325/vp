from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from tests.support.fake_torch import make_oom_torch

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import prepare_real_rawvsr_models as preparation  # noqa: E402

pytestmark = pytest.mark.pytorch


@pytest.mark.parametrize(
    ("scale_factor", "state_entries", "parameter_count"),
    [(2, 314, 6_143_599), (3, 314, 6_328_239), (4, 316, 6_291_311)],
)
def test_basicvsr_network_preserves_official_checkpoint_shape(
    scale_factor: int,
    state_entries: int,
    parameter_count: int,
) -> None:
    from app.algorithms.pytorch.real_rawvsr_basicvsr.network import _BasicVSRNet

    model = _BasicVSRNet(scale=scale_factor)

    assert len(model.state_dict()) == state_entries
    assert sum(parameter.numel() for parameter in model.parameters()) == parameter_count
    assert "spynet.basic_module.0.basic_module.0.conv.weight" in model.state_dict()
    assert "backward_resblocks.main.2.29.conv2.weight" in model.state_dict()


def test_basicvsr_rgb_and_boundary_padding_preserve_logical_frames() -> None:
    from app.algorithms.pytorch.real_rawvsr_basicvsr.runner import (
        _pad_temporal_sequence,
    )
    from app.algorithms.pytorch.real_rawvsr.rgb_frames import RgbTensorCodec

    frames = [np.full((2, 3, 3), value, dtype=np.uint8) for value in (10, 20, 30)]
    padded, offset = _pad_temporal_sequence(frames, minimum_frames=5)

    assert len(padded) == 5
    assert offset == 1
    assert padded[0] is frames[0]
    assert padded[-1] is frames[-1]
    codec = RgbTensorCodec("Real-RawVSR BasicVSR", minimum_size=64, size_multiple=1, scale_factor=2)
    prepared = codec.prepare(frames[:1])
    assert prepared is not None
    spatial = prepared.frames[0]
    assert spatial.shape == (64, 64, 3)
    assert np.array_equal(spatial[-1, -1], frames[0][-1, -1])

    with pytest.raises(ValueError, match="RGB uint8"):
        codec.prepare([np.zeros((2, 3, 3), dtype=np.float32)])


def test_basicvsr_rejects_unsupported_scale_and_engine() -> None:
    from app.algorithms.pytorch.real_rawvsr.sequence_adapter import build_model_load_spec

    with pytest.raises(ValueError, match="only 2x, 3x, 4x"):
        build_model_load_spec(
            algorithm_id="real-rawvsr-basicvsr",
            scale_factor=5,
            num_frames=10,
            engine="cuda",
            model_root="models",
        )
    with pytest.raises(ValueError, match="only CUDA"):
        build_model_load_spec(
            algorithm_id="real-rawvsr-basicvsr",
            scale_factor=2,
            num_frames=10,
            engine="tensorrt",
            model_root="models",
        )


def test_basicvsr_maps_cuda_oom_to_actionable_process_error() -> None:
    from app.algorithms.pytorch.real_rawvsr.sequence_adapter import build_model_load_spec
    from app.algorithms.pytorch.real_rawvsr_basicvsr.runner import RealRawVsrBasicVsr

    fake_torch, fail_oom, fake_cuda = make_oom_torch()
    spec = build_model_load_spec(
        algorithm_id="real-rawvsr-basicvsr",
        scale_factor=2,
        num_frames=10,
        engine="cuda",
        model_root="models",
    )
    algorithm = RealRawVsrBasicVsr(spec=spec, model_loader=lambda _spec, _path: (fake_torch, fail_oom))
    algorithm._torch = fake_torch
    algorithm._model = fail_oom

    with pytest.raises(ProcessError) as exc_info:
        algorithm.process_frames([np.zeros((64, 64, 3), dtype=np.uint8)])

    assert exc_info.value.code == TaskErrorCode.PROCESS_FAILED
    assert "lower the super-resolution frame chunk size" in exc_info.value.message
    assert exc_info.value.details == {"numFrames": 10, "scaleFactor": 2}
    assert fake_cuda.cleared


def test_safetensors_conversion_is_deterministic_and_omits_training_state(tmp_path: Path) -> None:
    import torch
    from safetensors.torch import load

    checkpoint = tmp_path / "best.pth"
    torch.save(
        {
            "state_dict": {"weight": torch.arange(4, dtype=torch.float32)},
            "optimizer": {"state": {"secret": torch.ones(1)}},
            "random_state": torch.get_rng_state(),
        },
        checkpoint,
    )

    first, first_parameters = preparation._serialize_state_dict(checkpoint)
    second, second_parameters = preparation._serialize_state_dict(checkpoint)

    assert first == second
    assert first_parameters == second_parameters == 4
    assert set(load(first)) == {"weight"}


def test_safetensors_conversion_rejects_nondeterministic_serialization(tmp_path: Path, monkeypatch) -> None:
    import safetensors.torch
    import torch

    checkpoint = tmp_path / "best.pth"
    torch.save({"state_dict": {"weight": torch.ones(1)}}, checkpoint)
    serialized = iter((b"first", b"second"))
    monkeypatch.setattr(safetensors.torch, "save", lambda *_args, **_kwargs: next(serialized))

    with pytest.raises(RuntimeError, match="not deterministic"):
        preparation._serialize_state_dict(checkpoint)
