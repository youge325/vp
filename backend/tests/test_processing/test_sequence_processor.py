import queue
import threading

import numpy as np

from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor import (
    _PipelineAlgorithms,
    _StepAlgorithm,
    _process_sequence_stream,
)
from app.processing.streaming.queues import DecodedFrame, EncodedFrame, StreamEnd, _DECODE_END, _ENCODE_END


class _SequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames):
        return [frame + 1 for frame in frames]


def test_process_sequence_stream_applies_sequence_stage_and_preserves_order():
    decode_queue = queue.Queue()
    encode_queue = queue.Queue()
    stop_event = threading.Event()
    frames = [
        np.zeros((2, 2, 3), dtype=np.uint8),
        np.ones((2, 2, 3), dtype=np.uint8),
    ]
    for index, frame in enumerate(frames):
        decode_queue.put(DecodedFrame(source_index=index, frame=frame))
    decode_queue.put(_DECODE_END)

    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    progress_calls = []
    stage_plan = StagePlan(
        pre_steps=[step],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=2,
        total_encoded_frames=2,
        total_pairs=1,
    )

    _process_sequence_stream(
        stage_plan=stage_plan,
        algorithms=_PipelineAlgorithms(
            pre=[_StepAlgorithm(step=step, backend=None, algorithm=_SequenceAlgorithm())],
            interpolation=None,
            post=[],
        ),
        progress_callbacks=[lambda current, total: progress_calls.append((current, total))],
        source_frames=2,
        resume_output_frames=0,
        decode_queue=decode_queue,
        encode_queue=encode_queue,
        stop_event=stop_event,
        metrics=PipelineMetrics(),
    )

    first = encode_queue.get_nowait()
    second = encode_queue.get_nowait()
    end = encode_queue.get_nowait()
    sentinel = encode_queue.get_nowait()

    assert isinstance(first, EncodedFrame)
    assert first.output_index == 0
    assert np.array_equal(first.frame, frames[0] + 1)
    assert isinstance(second, EncodedFrame)
    assert second.output_index == 1
    assert np.array_equal(second.frame, frames[1] + 1)
    assert isinstance(end, StreamEnd)
    assert sentinel is _ENCODE_END
    assert progress_calls == [(1, 2), (2, 2)]
