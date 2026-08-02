from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pytest

from app.algorithms.pytorch.real_rawvsr.fixed_window import _centered_window_indices
from app.algorithms.pytorch.real_rawvsr.rgb_frames import prepare_rgb_frames
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from tests.support.fake_torch import make_oom_torch
from app.generated.model_assets import REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM

pytestmark = pytest.mark.pytorch


@pytest.mark.parametrize(
    ("algorithm_id", "module_name", "class_name", "state_entries"),
    [
        ("real-rawvsr-edvr", "app.algorithms.pytorch.real_rawvsr.edvr", "_EdvrNet", (142, 142, 144)),
        ("real-rawvsr-tdan", "app.algorithms.pytorch.real_rawvsr.tdan", "_TdanNet", (95, 95, 97)),
        ("real-rawvsr-toflow", "app.algorithms.pytorch.real_rawvsr.toflow", "_ToFlowNet", (114, 114, 114)),
    ],
)
def test_fixed_window_networks_preserve_all_official_checkpoint_keys_and_parameter_counts(
    algorithm_id: str,
    module_name: str,
    class_name: str,
    state_entries: tuple[int, int, int],
) -> None:
    import importlib

    model_class = getattr(importlib.import_module(module_name), class_name)
    family = REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM[algorithm_id]
    for index, variant in enumerate(family.variants):
        state = model_class(scale=variant.scale_factor).state_dict()
        assert len(state) == state_entries[index]
        assert sum(tensor.numel() for tensor in state.values()) == variant.parameter_count


def test_edvr_and_tdan_share_torchvision_checkpoint_compatible_dcn_surface() -> None:
    from app.algorithms.pytorch.real_rawvsr.dcn import ModulatedDeformConvPack

    layer = ModulatedDeformConvPack(64, 64, 3, padding=1, deformable_groups=8, extra_offset_mask=True)
    state = layer.state_dict()

    assert set(state) == {"weight", "bias", "conv_offset_mask.weight", "conv_offset_mask.bias"}
    assert state["conv_offset_mask.weight"].shape == (216, 64, 3, 3)


def test_toflow_has_no_mmcv_registry_or_checkpoint_dependency() -> None:
    from app.algorithms.pytorch.real_rawvsr import toflow

    tree = ast.parse(inspect.getsource(toflow))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    assert not any(name == "mmcv" or name.startswith("mmcv.") for name in imports)


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (1, ((0, 0, 0, 0, 0),)),
        (2, ((0, 0, 0, 1, 1), (0, 0, 1, 1, 1))),
        (3, ((0, 0, 0, 1, 2), (0, 0, 1, 2, 2), (0, 1, 2, 2, 2))),
        (4, ((0, 0, 0, 1, 2), (0, 0, 1, 2, 3), (0, 1, 2, 3, 3), (1, 2, 3, 3, 3))),
        (5, ((0, 0, 0, 1, 2), (0, 0, 1, 2, 3), (0, 1, 2, 3, 4), (1, 2, 3, 4, 4), (2, 3, 4, 4, 4))),
    ],
)
def test_fixed_window_replicates_boundaries_for_one_to_five_frames(
    total: int,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    assert tuple(_centered_window_indices(index, total, 2) for index in range(total)) == expected


def test_fixed_window_pads_odd_dimensions_to_sixteen_and_crops_by_declared_scale() -> None:
    frame = np.arange(17 * 31 * 3, dtype=np.uint8).reshape(17, 31, 3)
    prepared = prepare_rgb_frames(
        [frame],
        "Real-RawVSR EDVR",
        minimum_size=16,
        spatial_modulo=16,
    )
    assert prepared is not None
    padded = prepared.frames[0]

    assert padded.shape == (32, 32, 3)
    assert np.array_equal(padded[-1, -1], frame[-1, -1])
    for scale in (2, 3, 4):
        projected = np.empty((padded.shape[0] * scale, padded.shape[1] * scale, 3), dtype=np.uint8)
        assert projected[: frame.shape[0] * scale, : frame.shape[1] * scale].shape == (17 * scale, 31 * scale, 3)


def test_fixed_window_model_sources_are_repository_owned() -> None:
    source_root = Path(__file__).resolve().parents[2] / "app/algorithms/pytorch/real_rawvsr"
    assert {path.name for path in source_root.glob("*.py")} >= {
        "dcn.py",
        "edvr.py",
        "factory.py",
        "fixed_window.py",
        "tdan.py",
        "toflow.py",
    }


def test_fixed_window_rejects_editable_frame_count_non_cuda_and_unknown_scale() -> None:
    from app.algorithms.pytorch.real_rawvsr.fixed_window import RealRawVsrFixedWindow

    arguments = {
        "algorithm_id": "real-rawvsr-edvr",
        "scale_factor": 2,
        "num_frames": 5,
        "engine": "cuda",
        "model_root": "models",
        "model_loader": lambda _scale, _path: (None, None),
    }
    with pytest.raises(ValueError, match="exactly 5 frames"):
        RealRawVsrFixedWindow(**{**arguments, "num_frames": 4})
    with pytest.raises(ValueError, match="only CUDA"):
        RealRawVsrFixedWindow(**{**arguments, "engine": "tensorrt"})
    with pytest.raises(ValueError, match="only 2x, 3x, and 4x"):
        RealRawVsrFixedWindow(**{**arguments, "scale_factor": 5})


def test_fixed_window_maps_cuda_oom_to_algorithm_specific_process_error() -> None:
    from app.algorithms.pytorch.real_rawvsr.fixed_window import RealRawVsrFixedWindow

    fake_torch, fail_oom, fake_cuda = make_oom_torch()
    algorithm = RealRawVsrFixedWindow(
        algorithm_id="real-rawvsr-edvr",
        scale_factor=4,
        num_frames=5,
        engine="cuda",
        model_root="models",
        model_loader=lambda _scale, _path: (fake_torch, fail_oom),
    )
    algorithm._torch = fake_torch
    algorithm._model = fail_oom

    with pytest.raises(ProcessError) as exc_info:
        algorithm.process_frames([np.zeros((17, 31, 3), dtype=np.uint8)])

    assert exc_info.value.code == TaskErrorCode.PROCESS_FAILED
    assert "Real-RawVSR EDVR x4" in exc_info.value.message
    assert "lower the input resolution or select a lighter" in exc_info.value.message
    assert exc_info.value.details == {"algorithm": "real-rawvsr-edvr", "scaleFactor": 4}
    assert fake_cuda.cleared
