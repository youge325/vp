import json
import re
import time

import pytest

from app.protocol.reporter import CliProgressReporter

_PROGRESS_PREFIX = "[VP_PROGRESS]"


def _terminal_progress_line(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.startswith(_PROGRESS_PREFIX)]
    assert lines, f"No terminal progress line found in stderr:\n{stderr}"
    return lines[-1]


def test_update_without_external_fps_uses_observed_progress_fps(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = CliProgressReporter(100)
    reporter.started_at = time.time() - 10

    reporter.update(20)

    line = _terminal_progress_line(capsys.readouterr().err)
    assert "--.- fps" not in line
    assert re.search(r"\|\s+\d+\.\d fps\s+\|", line)


def test_update_prefers_explicit_ffmpeg_fps(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = CliProgressReporter(100)
    reporter.started_at = time.time() - 100

    reporter.update(20, fps=48.0)

    line = _terminal_progress_line(capsys.readouterr().err)
    assert "48.0 fps" in line


def test_update_at_zero_progress_emits_structured_progress_without_terminal_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = CliProgressReporter(100)
    reporter.started_at = time.time() - 10

    reporter.update(0)

    captured = capsys.readouterr()
    stderr_lines = [line for line in captured.err.splitlines() if line.startswith(_PROGRESS_PREFIX)]
    stdout_lines = [json.loads(line) for line in captured.out.splitlines()]

    assert stderr_lines == []
    assert stdout_lines[-1]["current"] == 0
    assert stdout_lines[-1]["percent"] == 0.0


def test_stage_switch_allows_second_stage_to_restart_at_zero_without_terminal_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = CliProgressReporter(100)

    reporter.set_stage("01_frame_interpolation", 1, 2, total_frames=2)
    reporter.update(2, total_frames=2)
    reporter.set_stage("02_super_resolution", 2, 2, total_frames=10)
    reporter.update(0, total_frames=10)

    captured = capsys.readouterr()
    stderr_lines = [line for line in captured.err.splitlines() if line.startswith(_PROGRESS_PREFIX)]
    stdout_lines = [json.loads(line) for line in captured.out.splitlines()]

    assert len(stderr_lines) == 1
    assert stderr_lines[-1].startswith("[VP_PROGRESS] [1/2 01_frame_interpolation]")
    assert "100.0% 2/2" in stderr_lines[-1]
    assert stdout_lines[-1] == {
        "type": "progress",
        "current": 0,
        "total": 10,
        "percent": 0.0,
        "stage": "02_super_resolution",
        "stageIndex": 2,
        "stageTotal": 2,
    }


def test_update_at_stage_total_forces_final_progress(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = CliProgressReporter(100)
    reporter.set_stage("01_frame_interpolation", 1, 1, total_frames=100)

    reporter.update(99, total_frames=100)
    reporter.update(100, total_frames=100)

    captured = capsys.readouterr()
    stderr_lines = [line for line in captured.err.splitlines() if line.startswith(_PROGRESS_PREFIX)]
    stdout_lines = [json.loads(line) for line in captured.out.splitlines()]

    assert "100.0% 100/100" in stderr_lines[-1]
    assert stdout_lines[-1]["current"] == 100
    assert stdout_lines[-1]["percent"] == 100.0


def test_finish_uses_stage_total_without_processed_frame_argument(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = CliProgressReporter(100)
    reporter.set_stage("02_super_resolution", 2, 2, total_frames=25)

    reporter.finish()

    captured = capsys.readouterr()
    stderr_line = _terminal_progress_line(captured.err)
    stdout_lines = [json.loads(line) for line in captured.out.splitlines()]

    assert "100.0% 25/25" in stderr_line
    assert stdout_lines[-1] == {
        "type": "progress",
        "current": 25,
        "total": 25,
        "percent": 100.0,
        "stage": "02_super_resolution",
        "stageIndex": 2,
        "stageTotal": 2,
    }


def test_heartbeat_forces_same_progress_with_runtime_status(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = CliProgressReporter(100)
    reporter.set_stage("02_super_resolution", 2, 2, total_frames=10)
    reporter.update(0, total_frames=10)

    reporter.update(0, total_frames=10, heartbeat=True)

    captured = capsys.readouterr()
    stderr_lines = [line for line in captured.err.splitlines() if line.startswith(_PROGRESS_PREFIX)]
    stdout_lines = [json.loads(line) for line in captured.out.splitlines()]

    assert stderr_lines == []
    assert stdout_lines[-1]["current"] == 0
    assert stdout_lines[-1]["stage"] == "02_super_resolution"
