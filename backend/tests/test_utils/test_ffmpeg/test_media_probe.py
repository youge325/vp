"""Media metadata probe tests."""

import json
from types import SimpleNamespace

from app.utils.ffmpeg import media_probe


def test_media_metadata_helpers_read_primary_streams() -> None:
    info = {
        "format": {"duration": "2.5"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "r_frame_rate": "60000/1001",
                "width": 1920,
                "height": 1080,
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }

    assert media_probe.get_fps(info) == 59.94
    assert media_probe.get_duration(info) == 2.5
    assert media_probe.has_audio(info) is True
    assert media_probe.get_primary_video_codec(info) == "hevc"
    assert media_probe.get_primary_video_dimensions(info) == (1920, 1080)


def test_primary_video_dimensions_default_to_zero_without_video_stream() -> None:
    assert media_probe.get_primary_video_dimensions({"streams": [{"codec_type": "audio"}]}) == (0, 0)


def test_probe_video_info_returns_decoded_document(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    calls = []

    def fake_run(command):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps({"streams": []}))

    monkeypatch.setattr(media_probe, "run_ffmpeg_command", fake_run)
    assert media_probe.probe_video_info("ffprobe", str(input_path)) == {"streams": []}
    assert len(calls) == 1


def test_get_frame_count_prefers_metadata_without_scan(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    monkeypatch.setattr(
        media_probe,
        "run_ffmpeg_command",
        lambda _command: (_ for _ in ()).throw(AssertionError("unexpected frame scan")),
    )

    frame_count = media_probe.probe_frame_count(
        "ffprobe",
        str(input_path),
        {"streams": [{"codec_type": "video", "nb_frames": "120"}]},
        4.0,
        30.0,
    )

    assert frame_count == 120


def test_get_frame_count_falls_back_to_duration_for_invalid_scan(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")
    monkeypatch.setattr(media_probe, "run_ffmpeg_command", lambda _command: SimpleNamespace(stdout="not-json"))

    assert media_probe.probe_frame_count("ffprobe", str(input_path), {}, 2.5, 24.0) == 60
