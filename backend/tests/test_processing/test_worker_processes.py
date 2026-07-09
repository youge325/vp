from __future__ import annotations

import app.processing.streaming.worker_processes as worker_processes


def test_worker_processes_keeps_backend_dir_private() -> None:
    assert not hasattr(worker_processes, "backend_dir")
