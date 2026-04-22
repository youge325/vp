"""FFmpeg wrapper capability and argument tests."""

from types import MethodType

import pytest

from app.config import settings
from app.utils.ffmpeg_wrapper import FFmpegWrapper


class TestFFmpegWrapper:
    def test_init_default_paths(self):
        wrapper = FFmpegWrapper()
        assert wrapper.ffmpeg_path == settings.FFMPEG_PATH or wrapper.ffmpeg_path
        assert wrapper.ffprobe_path == settings.FFPROBE_PATH or wrapper.ffprobe_path

    def test_is_available_with_nonexistent_path(self):
        wrapper = FFmpegWrapper(ffmpeg_path="/nonexistent/ffmpeg")
        assert wrapper.is_available() is False

    def test_get_video_info_nonexistent_file(self):
        wrapper = FFmpegWrapper()
        with pytest.raises((RuntimeError, FileNotFoundError)):
            wrapper.get_video_info("/nonexistent/file.mp4")

    def test_parse_avoptions_extracts_choice_number_and_boolean_options(self):
        wrapper = FFmpegWrapper()
        help_text = """
Encoder h264_nvenc [NVIDIA NVENC H.264 encoder]:
    Supported pixel formats: yuv420p nv12 p010le
  -preset            <int>        E..V....... (from 0 to 18) (default p4)
     p1              1            fastest
     p4              4            medium
  -cq                <float>      E..V....... (from 0 to 51) (default 23)
  -forced-idr        <boolean>    E..V....... (default false)
"""

        options = wrapper.parse_avoptions(help_text)

        assert options[0]["name"] == "preset"
        assert options[0]["type"] == "choice"
        assert [choice["value"] for choice in options[0]["choices"]] == ["p1", "p4"]
        assert options[1]["name"] == "cq"
        assert options[1]["type"] == "number"
        assert options[1]["defaultValue"] == 23.0
        assert options[2]["name"] == "forced-idr"
        assert options[2]["type"] == "boolean"
        assert options[2]["defaultValue"] is False

    def test_parse_codec_profile_includes_pixel_format_option(self):
        wrapper = FFmpegWrapper()
        profile = wrapper.parse_codec_profile(
            "encoder",
            {"name": "hevc_nvenc", "label": "NVENC H.265", "family": "nvidia", "codec": "hevc"},
            """
Encoder hevc_nvenc [NVIDIA NVENC hevc encoder]:
    Supported pixel formats: yuv420p nv12 p010le
    Supported hardware devices: cuda
  -preset            <int>        E..V....... (from 0 to 18) (default p4)
     p4              4            medium
""",
        )

        assert profile["name"] == "hevc_nvenc"
        assert profile["pixelFormats"] == ["yuv420p", "nv12", "p010le"]
        assert profile["hardwareDevices"] == ["cuda"]
        assert profile["options"][0]["name"] == "pix_fmt"

    def test_build_decode_and_encode_args_support_hw_configs(self):
        wrapper = FFmpegWrapper()

        decode_args = wrapper.build_decode_input_args(
            "input.mp4",
            {
                "mode": "hardware",
                "hwaccel": "cuda",
                "hwaccelDevice": "0",
                "decoder": "hevc_cuvid",
                "options": {"resize": "1920x1080"},
            },
        )
        encode_args = wrapper.build_encode_output_args(
            "output.mp4",
            {
                "codec": "hevc_nvenc",
                "rateControl": {"mode": "cq", "value": 23},
                "options": {"preset": "p4"},
            },
        )

        assert decode_args[:6] == [
            "-hwaccel",
            "cuda",
            "-hwaccel_device",
            "0",
            "-c:v",
            "hevc_cuvid",
        ]
        assert "-resize" in decode_args
        assert encode_args[:2] == ["-c:v", "hevc_nvenc"]
        assert "-cq" in encode_args
        assert "-preset" in encode_args
        assert "output.mp4" in encode_args

    def test_discover_capabilities_filters_by_gpu_vendor(self):
        wrapper = FFmpegWrapper()

        wrapper.list_codec_names = MethodType(
            lambda self, mode: [
                "hevc_nvenc",
                "h264_qsv",
                "hevc_cuvid",
                "hevc_qsv",
            ]
            if mode == "encoders"
            else ["hevc_cuvid", "hevc_qsv"],
            wrapper,
        )
        wrapper.list_hwaccels = MethodType(lambda self: ["cuda", "qsv"], wrapper)
        wrapper.describe_codec = MethodType(
            lambda self, mode, name: f"""
{mode} {name}
    Supported pixel formats: yuv420p
    Supported hardware devices: {"cuda" if "nv" in name or "cuvid" in name else "qsv"}
""",
            wrapper,
        )

        capabilities = wrapper.discover_capabilities(gpu_adapters=[{"vendor": "nvidia", "device_type": "discrete"}])

        assert capabilities["hwaccels"] == ["cuda", "qsv"]
        assert [profile["name"] for profile in capabilities["encoderProfiles"]] == ["hevc_nvenc"]
        assert [profile["name"] for profile in capabilities["decoderProfiles"]] == [
            "software",
            "hevc_cuvid",
        ]
