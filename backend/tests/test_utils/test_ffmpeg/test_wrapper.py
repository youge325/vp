"""Production FFmpeg facade tests."""

import pytest

from app.config import settings
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import _parse_progress_snapshot


def test_init_uses_configured_paths() -> None:
    wrapper = FFmpegWrapper()

    assert wrapper.ffmpeg_path == settings.FFMPEG_PATH
    assert wrapper.ffprobe_path == settings.FFPROBE_PATH


def test_is_available_with_nonexistent_path() -> None:
    assert FFmpegWrapper(ffmpeg_path="/nonexistent/ffmpeg").is_available() is False


def test_get_video_info_nonexistent_file() -> None:
    with pytest.raises((RuntimeError, FileNotFoundError)):
        FFmpegWrapper().get_video_info("/nonexistent/file.mp4")


def test_wrapper_does_not_expose_internal_probe_or_builder_facades() -> None:
    removed_methods = {
        "list_codec_names",
        "list_hwaccels",
        "describe_codec",
        "parse_codec_profile",
        "parse_avoptions",
        "probe_rate_control_modes",
        "probe_decoder_hardware_devices",
        "probe_decoder_hardware_device_options",
        "build_decode_input_args",
        "build_encode_output_args",
        "decode_to_frames",
        "encode_from_frames",
    }

    assert not removed_methods.intersection(vars(FFmpegWrapper))


def test_parse_progress_snapshot_extracts_runtime_values() -> None:
    parsed = _parse_progress_snapshot(
        {
            "frame": "240",
            "fps": "59.9",
            "speed": "1.25x",
            "out_time_us": "4000000",
            "progress": "continue",
        }
    )

    assert parsed == {
        "frame": 240,
        "fps": 59.9,
        "speed": 1.25,
        "out_time_seconds": 4.0,
        "progress": "continue",
    }
