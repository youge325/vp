from __future__ import annotations

from app.processing.streaming import stage_runtime


def test_stage_runtime_does_not_reexport_stage_rule_helpers() -> None:
    assert not hasattr(stage_runtime, "algorithm_kwargs_for_create")
    assert "algorithm_kwargs_for_create" not in stage_runtime.__all__
