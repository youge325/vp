"""Streaming pipeline entry point.

The public surface is the :func:`process_video_streaming` orchestrator.
Runtime work is split across preflight, dispatch, stage-worker pipeline,
stage-file pipeline, and encoder-worker modules.
"""

from app.processing.streaming.pipeline import process_video_streaming

__all__ = ["process_video_streaming"]
