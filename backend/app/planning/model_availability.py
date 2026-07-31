"""Consumer-owned port for stage model availability checks."""

from __future__ import annotations

from typing import Protocol

from app.planning.processing_steps import ProcessingStep


class ModelAvailabilityPort(Protocol):
    def validate(self, step: ProcessingStep) -> None:
        """Raise a domain error when the selected model is unavailable."""


__all__ = ["ModelAvailabilityPort"]
