from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.ffmpeg_media import FFmpegMediaAdapter
from app.ports.media import VideoInspection, VideoMetadata


class _Writer:
    output_frame_count = 0

    def write_frame(self, _frame) -> None:
        return None

    def close(self) -> None:
        return None


def _raw_info() -> dict[str, object]:
    return {
        "format": {"duration": "2.0"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 320,
                "height": 180,
                "r_frame_rate": "24/1",
                "nb_frames": "48",
            },
            {"codec_type": "audio"},
        ],
    }


def _raw_info_without_frame_count() -> dict[str, object]:
    info = _raw_info()
    streams = info["streams"]
    assert isinstance(streams, list)
    video_stream = streams[0]
    assert isinstance(video_stream, dict)
    del video_stream["nb_frames"]
    return info


def test_probe_video_hides_raw_ffprobe_shape_behind_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    probes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.adapters.ffmpeg_media._media_probe.probe_video_info",
        lambda ffprobe, input_path: probes.append((ffprobe, input_path)) or _raw_info(),
    )
    adapter = FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin")

    assert adapter.probe_video("input.mp4") == VideoMetadata(
        width=320,
        height=180,
        source_fps=24.0,
        source_frames=48,
        duration=2.0,
        has_audio=True,
    )
    assert probes == [("ffprobe-bin", "input.mp4")]


def test_adapter_reuses_one_metadata_probe_across_consumer_ports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    commands: list[list[str]] = []

    def run(command: list[str]) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(stdout=json.dumps(_raw_info()))

    monkeypatch.setattr("app.utils.ffmpeg.media_probe.run_ffmpeg_command", run)
    adapter = FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin")

    assert adapter.probe_video(str(input_path)).source_frames == 48
    assert adapter.inspect_video(str(input_path)).video_codec == "h264"
    assert adapter.get_frame_count(str(input_path)) == 48
    assert commands == [
        [
            "ffprobe-bin",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]
    ]


def test_adapter_runs_supplemental_frame_scan_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    commands: list[list[str]] = []

    def run(command: list[str]) -> SimpleNamespace:
        commands.append(command)
        payload = (
            {"streams": [{"nb_read_frames": "47"}]} if "-count_frames" in command else _raw_info_without_frame_count()
        )
        return SimpleNamespace(stdout=json.dumps(payload))

    monkeypatch.setattr("app.utils.ffmpeg.media_probe.run_ffmpeg_command", run)
    adapter = FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin")

    assert adapter.inspect_video(str(input_path)).fps == 24.0
    assert adapter.get_frame_count(str(input_path)) == 47
    assert adapter.probe_video(str(input_path)).source_frames == 47
    assert sum("-count_frames" in command for command in commands) == 1
    assert len(commands) == 2


def test_adapter_invalidates_probe_snapshot_when_file_identity_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"first")
    calls = 0

    def probe(_ffprobe: str, _input_path: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _raw_info()

    monkeypatch.setattr("app.adapters.ffmpeg_media._media_probe.probe_video_info", probe)
    adapter = FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin")

    adapter.inspect_video(str(input_path))
    input_path.write_bytes(b"second-version")
    adapter.inspect_video(str(input_path))

    assert calls == 2


def test_video_inspection_port_projects_wire_neutral_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.adapters.ffmpeg_media._media_probe.probe_video_info",
        lambda _ffprobe, _input_path: _raw_info(),
    )

    assert FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin").inspect_video("input.mp4") == VideoInspection(
        fps=24.0,
        width=320,
        height=180,
        video_codec="h264",
    )


def test_encoder_progress_is_translated_at_the_adapter_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "app.adapters.ffmpeg_media._open_rawvideo_encoder",
        lambda _path, **kwargs: captured.update(kwargs) or _Writer(),
    )
    monkeypatch.setattr(
        "app.adapters.ffmpeg_media._encode.build_encode_output_args",
        lambda _path, _config: [],
    )
    adapter = FFmpegMediaAdapter("ffmpeg-bin", "ffprobe-bin")
    events: list[tuple[int, float | None, float | None, float | None, str]] = []

    adapter.open_rawvideo_encoder(
        output_path="chunk.mp4",
        width=320,
        height=180,
        fps=24.0,
        progress_callback=lambda *event: events.append(event),
        progress_frame_offset=100,
    )
    callback = captured["progress_callback"]
    assert callback is not None
    callback(
        {
            "frame": 25,
            "fps": 24.0,
            "speed": 1.5,
            "out_time_seconds": 1.0,
            "progress": "continue",
        }
    )

    assert events == [(125, 24.0, 1.5, 1.0, "continue")]
