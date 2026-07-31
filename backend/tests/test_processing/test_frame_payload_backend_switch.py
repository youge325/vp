import numpy as np

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


class _Backend:
    def __init__(self, name: str):
        self.name = name

    def numpy_to_tensor(self, frame):
        return (self.name, frame.copy())

    def tensor_to_numpy(self, tensor):
        return tensor[1].copy()


def test_frame_payload_converts_between_different_tensor_backends_via_numpy():
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    first = _Backend("onnx")
    second = _Backend("paddle")
    payload = FramePayload.from_tensor(first.numpy_to_tensor(frame), first)

    converted = payload.ensure_tensor(second, PipelineMetrics())

    assert converted[0] == "paddle"
    assert np.array_equal(converted[1], frame)
