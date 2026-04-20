"""帧处理过滤器测试。"""

from pathlib import Path

import numpy as np
from PIL import Image

from app.algorithms.base import IAlgorithm
from app.processing.frame_processor import FrameProcessFilter


class _IdentityTensorBackend:
    def numpy_to_tensor(self, frame):
        return frame

    def tensor_to_numpy(self, tensor):
        return tensor

    def get_name(self) -> str:
        return "identity"


class _IdentityAlgorithm(IAlgorithm):
    def process_frame(self, frame, **kwargs):
        return frame

    def process_frame_batch(self, frames: list, **kwargs) -> list:
        return frames

    def get_name(self) -> str:
        return "identity"

    def validate(self) -> bool:
        return True


def _write_frame(frame_dir: Path, index: int) -> None:
    image = np.full((8, 8, 3), index * 40, dtype=np.uint8)
    Image.fromarray(image).save(frame_dir / f"frame_{index:06d}.png")


def test_single_frame_processing_uses_unique_stage_output_dirs(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    _write_frame(frame_dir, 1)
    _write_frame(frame_dir, 2)

    first_filter = FrameProcessFilter(
        algorithm=_IdentityAlgorithm(),
        stage_name="01_super_resolution",
    )
    first_filter._tensor_backend = _IdentityTensorBackend()

    context = {}
    first_result = first_filter.process(
        {
            "frame_dir": str(frame_dir),
            "frame_prefix": "frame_%06d.png",
        },
        context,
    )

    second_filter = FrameProcessFilter(
        algorithm=_IdentityAlgorithm(),
        stage_name="02_super_resolution",
    )
    second_filter._tensor_backend = _IdentityTensorBackend()
    second_result = second_filter.process(first_result, context)

    assert first_result["frame_dir"] != second_result["frame_dir"]
    assert first_result["frame_prefix"] == "frame_%06d.png"
    assert second_result["frame_prefix"] == "frame_%06d.png"
    assert Path(first_result["frame_dir"]).name == "processed_01_super_resolution"
    assert Path(second_result["frame_dir"]).name == "processed_02_super_resolution"
