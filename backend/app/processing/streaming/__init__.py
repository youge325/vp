"""Streaming pipeline entry point.

Splits the original monolithic ``processing/streaming.py`` into focused
sub-modules: ``queues``, ``decoder``, ``processor``, ``encoder``, and
``pipeline``.  Public surface is the single :func:`process_video_streaming`
orchestrator.
"""

from app.processing.streaming.pipeline import process_video_streaming

__all__ = ["process_video_streaming"]
