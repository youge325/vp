from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app.utils.late_cleanup import _LateCleanupCoordinator


def test_never_successful_late_cleanup_stops_at_its_original_deadline(caplog: pytest.LogCaptureFixture) -> None:
    coordinator = _LateCleanupCoordinator(timeout_seconds=0.05, retry_interval_seconds=0.001)
    deadlines: list[float] = []

    class NeverReapedOwner:
        def retry_cleanup(self, *, deadline: float) -> bool:
            deadlines.append(deadline)
            return False

    owner = NeverReapedOwner()
    started_at = time.monotonic()
    coordinator.submit(owner)
    cleanup_thread = next(thread for thread in threading.enumerate() if thread.name == f"vp-late-cleanup-{id(owner)}")

    assert cleanup_thread.daemon is True
    coordinator.close()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.25
    assert deadlines
    assert len(set(deadlines)) == 1
    assert deadlines[0] - started_at == pytest.approx(0.05, abs=0.02)
    assert not cleanup_thread.is_alive()
    assert "exceeded the 0.050s termination deadline" in caplog.text
    with pytest.raises(RuntimeError, match="closed"):
        coordinator.submit(NeverReapedOwner())


def test_cli_composition_root_closes_the_loaded_cleanup_coordinator(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.__main__ as app_main

    closed: list[bool] = []
    module = SimpleNamespace(late_cleanup_coordinator=SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setitem(app_main.sys.modules, "app.utils.late_cleanup", module)

    app_main._close_late_cleanup()

    assert closed == [True]


def test_close_deadline_race_repeats_without_leaking_threads() -> None:
    class NeverReapedOwner:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()

        def retry_cleanup(self, *, deadline: float) -> bool:
            assert deadline > 0
            self.started.set()
            assert self.release.wait(timeout=1)
            return False

    for _attempt in range(100):
        coordinator = _LateCleanupCoordinator(timeout_seconds=0.002, retry_interval_seconds=0.0005)
        owner = NeverReapedOwner()
        coordinator.submit(owner)
        assert owner.started.wait(timeout=1)
        cleanup_thread = next(
            thread for thread in threading.enumerate() if thread.name == f"vp-late-cleanup-{id(owner)}"
        )

        owner.release.set()
        coordinator.close()

        assert not cleanup_thread.is_alive()

    assert not any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
