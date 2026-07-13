"""FFmpeg encode/decode argument builder tests."""

from pathlib import Path

from app.utils.ffmpeg import encode


def test_argument_builders_support_hardware_decode_and_encode_options() -> None:
    decode_args = encode.build_decode_input_args(
        "input.mp4",
        {
            "mode": "hardware",
            "hwaccel": "cuda",
            "hwaccelDevice": "0",
            "decoder": "hevc_cuvid",
            "options": {"resize": "1920x1080"},
        },
    )
    encode_args = encode.build_encode_output_args(
        "output.mp4",
        {
            "codec": "hevc_nvenc",
            "rateControl": {"mode": "cq", "value": 23},
            "options": {"preset": "p4"},
        },
    )

    assert decode_args[:6] == ["-hwaccel", "cuda", "-hwaccel_device", "0", "-c:v", "hevc_cuvid"]
    assert decode_args[-2:] == ["-i", "input.mp4"]
    assert "-resize" in decode_args
    assert encode_args[:2] == ["-c:v", "hevc_nvenc"]
    assert "-cq" in encode_args
    assert "-preset" in encode_args
    assert "output.mp4" in encode_args


def test_concat_videos_runs_command_and_removes_temporary_manifest(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []
    segment_path = tmp_path / "segment.mp4"
    segment_path.write_bytes(b"segment")
    output_path = tmp_path / "output.mp4"
    monkeypatch.setattr(encode, "run_ffmpeg_command", commands.append)

    encode.concat_videos("ffmpeg", [str(segment_path)], str(output_path))

    assert len(commands) == 1
    command = commands[0]
    manifest_path = Path(command[command.index("-i") + 1])
    assert str(output_path) in command
    assert not manifest_path.exists()


def test_extract_audio_reports_whether_the_requested_output_was_created(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "audio.aac"

    def create_output(_command: list[str]) -> None:
        output_path.write_bytes(b"audio")

    monkeypatch.setattr(encode, "run_ffmpeg_command", create_output)

    assert encode.extract_audio("ffmpeg", "input.mp4", str(output_path)) is True

    output_path.unlink()
    monkeypatch.setattr(encode, "run_ffmpeg_command", lambda _command: None)
    assert encode.extract_audio("ffmpeg", "input.mp4", str(output_path)) is False


def test_merge_audio_runs_as_a_command(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(encode, "run_ffmpeg_command", commands.append)

    result = encode.merge_audio("ffmpeg", "video.mp4", "audio.aac", "output.mp4")

    assert result is None
    assert commands[0][-2:] == ["output.mp4", "-y"]


def test_transcode_video_runs_non_progress_command(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(encode, "run_ffmpeg_command", commands.append)

    encode.transcode_video(
        "ffmpeg",
        decode_input_args=["-i", "input.mp4"],
        encode_output_args=["-c:v", "libx264", "output.mp4", "-y"],
        output_fps=60.0,
        keep_audio=False,
    )

    assert commands == [
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "input.mp4",
            "-map",
            "0:v:0",
            "-an",
            "-r",
            "60.0",
            "-c:v",
            "libx264",
            "output.mp4",
            "-y",
        ]
    ]
