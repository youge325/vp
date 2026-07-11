"""Rawvideo command rules owned by the FFmpeg I/O module."""

from app.utils.ffmpeg.io import _build_rawvideo_decode_command, _build_rawvideo_encode_command


def test_build_rawvideo_commands_include_pipe_and_geometry() -> None:
    decode_cmd = _build_rawvideo_decode_command(
        "ffmpeg",
        "input.mp4",
        width=1920,
        height=1080,
        decode_input_args=["-i", "input.mp4"],
        start_frame=25,
        frame_count=1000,
    )
    encode_cmd = _build_rawvideo_encode_command(
        "ffmpeg",
        "output.mp4",
        width=1920,
        height=1080,
        fps=48.0,
        output_fps=60.0,
        encode_output_args=["-c:v", "libx264", "output.mp4", "-y"],
    )

    assert decode_cmd[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
    assert "-vf" in decode_cmd
    assert "select=gte(n\\,25)" in decode_cmd
    assert "-frames:v" in decode_cmd
    assert "1000" in decode_cmd
    assert decode_cmd[-1] == "-"

    assert encode_cmd[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
    assert "-progress" in encode_cmd
    assert "pipe:2" in encode_cmd
    assert "-s" in encode_cmd
    assert "1920x1080" in encode_cmd
    assert "-framerate" in encode_cmd
    assert "48.0" in encode_cmd
    assert "-r" in encode_cmd
    assert "60.0" in encode_cmd
    assert "output.mp4" in encode_cmd
