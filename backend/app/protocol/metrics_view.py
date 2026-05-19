"""Read-side view contract for pipeline metrics.

Phase 10 — break the ``protocol → processing`` reverse import.

``CliProgressReporter`` only ever calls one method on the metrics object
it's handed (``.snapshot()``). Depending on ``PipelineMetrics`` directly
forced the layout ``app.protocol → app.processing.streaming`` — a
reversed layer dependency, since ``processing`` is the higher-level
consumer of ``protocol``'s NDJSON emitter.

Declaring ``MetricsSnapshot`` as a ``typing.Protocol`` here flips the
direction: ``protocol`` defines what it needs, ``processing`` happens to
satisfy it (structural typing — no nominal inheritance required). The
layering rule "protocol is a leaf" is restored and enforced by
``backend/tests/test_protocol/test_layering.py``.

Implementors elsewhere just need a ``snapshot()`` method returning a
dict of primitive values that can be serialised into the NDJSON
``progress`` frame.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MetricsSnapshot(Protocol):
    """Minimal contract ``CliProgressReporter`` needs from a metrics object.

    Anything providing ``snapshot() -> dict`` qualifies — most notably
    ``app.processing.streaming.metrics.PipelineMetrics``.
    """

    def snapshot(self) -> dict[str, Any]: ...


__all__ = ["MetricsSnapshot"]
