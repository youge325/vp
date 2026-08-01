"""Centralised NDJSON protocol emitter for the VP Workbench CLI.

All structured events written to stdout pass through the shared ``ndjson`` emitter
so the format, field names and envelope shape stay consistent across the
pipeline.  Ordinary log lines and terminal progress bars continue to go to
stderr and are *not* handled here.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from pydantic import BaseModel

from app.generated.protocol_constants import (
    BACKEND_ENVELOPE_OPTIONAL_FIELDS,
    BACKEND_ENVELOPE_PAYLOAD_TYPES,
    BACKEND_ENVELOPE_PRESERVES_DISCRIMINATOR,
    BackendEnvelopeType,
)
from app.protocol.encoding import encode_bounded_json_line


# Stream variants are constrained by ``contracts/ndjson.schema.json``.
# One-shot check/info/inspection envelopes are decoded only by their typed
# command adapters and therefore are not task-stream variants.
class _NdjsonEmitter:
    """Serialize complete NDJSON lines onto stdout.

    A dedicated lock covers serialization, write and flush. The GIL is not an
    I/O atomicity guarantee because stream writes may release it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _write(self, envelope: dict[str, Any]) -> None:
        line = encode_bounded_json_line(envelope)
        with self._lock:
            sys.stdout.write(line)
            sys.stdout.flush()

    def emit(self, event_type: BackendEnvelopeType, payload: BaseModel) -> None:
        expected_type = BACKEND_ENVELOPE_PAYLOAD_TYPES[event_type]
        if type(payload) is not expected_type:
            raise TypeError(f"{event_type.value} requires {expected_type.__name__}, got {type(payload).__name__}")

        data = payload.model_dump(by_alias=True, mode="json")
        for field in BACKEND_ENVELOPE_OPTIONAL_FIELDS[event_type]:
            if data.get(field) is None:
                data.pop(field, None)

        if event_type in BACKEND_ENVELOPE_PRESERVES_DISCRIMINATOR:
            discriminator = data.pop("type", None)
            if discriminator != event_type.value:
                raise ValueError(f"{event_type.value} payload discriminator is {discriminator!r}")
        elif "type" in data:
            raise ValueError(f"{event_type.value} payload must not define a discriminator")

        self._write({"type": event_type.value, **data})


# Module-level convenience alias
ndjson = _NdjsonEmitter()

__all__ = ["ndjson"]
