"""Compatibility entrypoint for the streaming encoder worker."""

from __future__ import annotations

from app.processing.streaming.encoder_worker import run_encoder_worker as _encoder_worker


__all__ = ["_encoder_worker"]
