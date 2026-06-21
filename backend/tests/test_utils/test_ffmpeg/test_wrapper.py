"""FFmpeg wrapper capability and argument tests."""

import subprocess
from types import MethodType

import pytest

from app.config import settings
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import _parse_progress_snapshot


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

    def test_build_rawvideo_commands_include_pipe_and_geometry(self):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        decode_cmd = wrapper.build_rawvideo_decode_command(
            "input.mp4",
            width=1920,
            height=1080,
            decode_config={"mode": "software", "decoder": "software", "options": {}},
            start_frame=25,
        )
        encode_cmd = wrapper.build_rawvideo_encode_command(
            "output.mp4",
            width=1920,
            height=1080,
            fps=48.0,
            output_fps=60.0,
            encode_config={"codec": "libx264", "rateControl": {"mode": "crf", "value": 18}, "options": {}},
        )

        assert decode_cmd[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
        assert "-vf" in decode_cmd
        assert "select=gte(n\\,25)" in decode_cmd
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

    def test_legacy_frame_directory_helpers_are_removed(self):
        assert not hasattr(FFmpegWrapper, "decode_to_frames")
        assert not hasattr(FFmpegWrapper, "encode_from_frames")

    def test_parse_progress_snapshot_extracts_frame_fps_speed_and_time(self):
        parsed = _parse_progress_snapshot(
            {
                "frame": "240",
                "fps": "59.9",
                "speed": "1.25x",
                "out_time_us": "4000000",
                "progress": "continue",
            }
        )

        assert parsed["frame"] == 240
        assert parsed["fps"] == 59.9
        assert parsed["speed"] == 1.25
        assert parsed["out_time_seconds"] == 4.0
        assert parsed["progress"] == "continue"

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
        wrapper.probe_decoder_hardware_devices = MethodType(
            lambda self, decoder, codec, candidates, hwaccels, encoder_names, probe_dir=None, sample_cache=None: list(
                candidates
            ),
            wrapper,
        )
        wrapper.probe_decoder_hardware_device_options = MethodType(
            lambda self, decoder, codec, devices, encoder_names, probe_dir=None, sample_cache=None: {
                device: [{"value": "0", "label": "0"}] for device in devices
            },
            wrapper,
        )

        capabilities = wrapper.discover_capabilities(gpu_adapters=[{"vendor": "nvidia", "device_type": "discrete"}])

        assert capabilities["hwaccels"] == ["cuda"]
        assert [profile["name"] for profile in capabilities["encoderProfiles"]] == ["hevc_nvenc"]
        assert [profile["name"] for profile in capabilities["decoderProfiles"]] == [
            "software",
            "hevc_cuvid",
        ]

    def test_probe_rate_control_modes_verifies_candidates_with_ffmpeg(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        modes = wrapper.probe_rate_control_modes(
            "libx264",
            [
                {"name": "crf", "defaultValue": 19},
                {"name": "qp", "defaultValue": 22},
            ],
        )

        assert [mode["mode"] for mode in modes] == ["crf", "qp", "bitrate"]
        assert modes[0] == {"mode": "crf", "label": "CRF", "defaultValue": 19, "unit": "CRF"}
        assert modes[1] == {"mode": "qp", "label": "QP", "defaultValue": 22, "unit": "QP"}
        assert modes[2] == {"mode": "bitrate", "label": "Bitrate", "defaultValue": 8, "unit": "Mbps"}

        assert len(calls) == 3
        assert ["-crf", "19"] in [calls[0][index : index + 2] for index in range(len(calls[0]) - 1)]
        assert ["-qp", "22"] in [calls[1][index : index + 2] for index in range(len(calls[1]) - 1)]
        assert ["-b:v", "8M"] in [calls[2][index : index + 2] for index in range(len(calls[2]) - 1)]
        assert "color=size=256x256:rate=1" in calls[0]
        assert all("-f" in call and "lavfi" in call and "null" in call for call in calls)

    def test_probe_rate_control_modes_drops_failed_modes_without_fallback(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            if "-cq" in cmd:
                raise RuntimeError("unsupported cq")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        modes = wrapper.probe_rate_control_modes(
            "h264_nvenc",
            [
                {"name": "cq", "defaultValue": 21},
                {"name": "qp", "defaultValue": 25},
            ],
        )

        assert [mode["mode"] for mode in modes] == ["qp", "bitrate"]

    def test_probe_rate_control_modes_uses_ui_defaults_for_unset_encoder_defaults(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        monkeypatch.setattr(
            "app.utils.ffmpeg.probe.run_ffmpeg_command",
            lambda cmd, *, timeout=3600: subprocess.CompletedProcess(cmd, 0, "", ""),
        )

        modes = wrapper.probe_rate_control_modes(
            "h264_nvenc",
            [
                {"name": "cq", "defaultValue": 0},
                {"name": "qp", "defaultValue": -1},
            ],
        )

        assert modes[0] == {"mode": "cq", "label": "CQ", "defaultValue": 23, "unit": "CQ"}
        assert modes[1] == {"mode": "qp", "label": "QP", "defaultValue": 23, "unit": "QP"}

    def test_probe_rate_control_modes_returns_empty_when_every_probe_fails(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            raise RuntimeError("encoder cannot be opened")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        modes = wrapper.probe_rate_control_modes(
            "broken_encoder",
            [{"name": "crf", "defaultValue": 18}],
        )

        assert modes == []

    def test_discover_capabilities_includes_rate_control_modes(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        wrapper.list_codec_names = MethodType(
            lambda self, mode: ["libx264"] if mode == "encoders" else [],
            wrapper,
        )
        wrapper.list_hwaccels = MethodType(lambda self: [], wrapper)
        wrapper.describe_codec = MethodType(
            lambda self, mode, name: """
Encoder libx264 [libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10]:
    Supported pixel formats: yuv420p
  -crf               <float>      E..V....... (from -1 to 51) (default 19)
""",
            wrapper,
        )

        monkeypatch.setattr(
            "app.utils.ffmpeg.probe.run_ffmpeg_command",
            lambda cmd, *, timeout=3600: subprocess.CompletedProcess(cmd, 0, "", ""),
        )

        capabilities = wrapper.discover_capabilities([])

        profile = capabilities["encoderProfiles"][0]
        assert profile["name"] == "libx264"
        assert [mode["mode"] for mode in profile["rateControlModes"]] == ["crf", "bitrate"]

    def test_probe_decoder_hardware_devices_verifies_candidates_with_ffmpeg(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        devices = wrapper.probe_decoder_hardware_devices(
            "h264_cuvid",
            "h264",
            ["cuda", "qsv", "d3d11va"],
            ["cuda", "qsv"],
            {"libx264"},
        )

        assert devices == ["cuda", "qsv"]
        assert len(calls) == 3
        assert calls[0][:9] == [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=256x256:rate=1",
        ]
        assert ["-c:v", "libx264"] in [calls[0][index : index + 2] for index in range(len(calls[0]) - 1)]

        verify_calls = calls[1:]
        assert [["-hwaccel", "cuda"], ["-hwaccel", "qsv"]] == [
            call[index : index + 2]
            for call in verify_calls
            for index in range(len(call) - 1)
            if call[index] == "-hwaccel"
        ]
        assert all(
            ["-c:v", "h264_cuvid"] in [call[index : index + 2] for index in range(len(call) - 1)]
            for call in verify_calls
        )
        assert all("-f" in call and "null" in call for call in verify_calls)
        assert all("-hwaccel_device" not in call for call in verify_calls)

    def test_probe_decoder_hardware_device_options_verifies_candidates_with_ffmpeg(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.DECODER_HARDWARE_DEVICE_PROBE_VALUES", ("0", "1"))
        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        options = wrapper.probe_decoder_hardware_device_options(
            "h264_cuvid",
            "h264",
            ["cuda", "qsv"],
            {"libx264"},
        )

        assert options == {
            "cuda": [{"value": "0", "label": "0"}, {"value": "1", "label": "1"}],
            "qsv": [{"value": "0", "label": "0"}, {"value": "1", "label": "1"}],
        }
        assert len(calls) == 5

        verify_calls = calls[1:]
        assert [["-hwaccel", "cuda"], ["-hwaccel", "cuda"], ["-hwaccel", "qsv"], ["-hwaccel", "qsv"]] == [
            call[index : index + 2]
            for call in verify_calls
            for index in range(len(call) - 1)
            if call[index] == "-hwaccel"
        ]
        assert [
            ["-hwaccel_device", "0"],
            ["-hwaccel_device", "1"],
            ["-hwaccel_device", "0"],
            ["-hwaccel_device", "1"],
        ] == [
            call[index : index + 2]
            for call in verify_calls
            for index in range(len(call) - 1)
            if call[index] == "-hwaccel_device"
        ]

    def test_probe_decoder_hardware_device_options_drops_failed_values_without_fallback(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            if "-hwaccel_device" in cmd and cmd[cmd.index("-hwaccel_device") + 1] == "1":
                raise RuntimeError("unsupported device index")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.DECODER_HARDWARE_DEVICE_PROBE_VALUES", ("0", "1"))
        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        options = wrapper.probe_decoder_hardware_device_options(
            "h264_cuvid",
            "h264",
            ["cuda"],
            {"libx264"},
        )

        assert options == {"cuda": [{"value": "0", "label": "0"}]}

    def test_probe_decoder_hardware_devices_drops_failed_devices_without_fallback(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            if "-hwaccel" in cmd and cmd[cmd.index("-hwaccel") + 1] == "qsv":
                raise RuntimeError("unsupported qsv")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        devices = wrapper.probe_decoder_hardware_devices(
            "h264_cuvid",
            "h264",
            ["cuda", "qsv"],
            ["cuda", "qsv"],
            {"libx264"},
        )

        assert devices == ["cuda"]

    def test_probe_decoder_hardware_devices_returns_empty_when_every_probe_fails(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            if "-hwaccel" in cmd:
                raise RuntimeError("decoder cannot use device")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        devices = wrapper.probe_decoder_hardware_devices(
            "hevc_qsv",
            "hevc",
            ["qsv"],
            ["qsv"],
            {"libx265"},
        )

        assert devices == []

    def test_probe_decoder_hardware_devices_returns_empty_without_sample_encoder(self, monkeypatch):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *, timeout: int = 3600):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("app.utils.ffmpeg.probe.run_ffmpeg_command", fake_run)

        devices = wrapper.probe_decoder_hardware_devices(
            "av1_cuvid",
            "av1",
            ["cuda"],
            ["cuda"],
            {"libx264"},
        )

        assert devices == []
        assert calls == []

    def test_discover_capabilities_includes_decoder_hardware_devices(self):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")
        probe_calls: list[tuple[str, str, list[str], list[str], set[str]]] = []
        option_probe_calls: list[tuple[str, str, list[str], set[str]]] = []

        wrapper.list_codec_names = MethodType(
            lambda self, mode: ["libx264"] if mode == "encoders" else ["h264_cuvid"],
            wrapper,
        )
        wrapper.list_hwaccels = MethodType(lambda self: ["cuda", "qsv"], wrapper)
        wrapper.describe_codec = MethodType(
            lambda self, mode, name: """
Decoder h264_cuvid [NVIDIA CUVID H.264 decoder]:
    Supported hardware devices: cuda qsv
""",
            wrapper,
        )

        def fake_probe(
            self,
            decoder,
            codec,
            candidates,
            hwaccels,
            encoder_names,
            probe_dir=None,
            sample_cache=None,
        ):
            probe_calls.append((decoder, codec, list(candidates), list(hwaccels), set(encoder_names)))
            return ["cuda"]

        wrapper.probe_decoder_hardware_devices = MethodType(fake_probe, wrapper)

        def fake_option_probe(
            self,
            decoder,
            codec,
            devices,
            encoder_names,
            probe_dir=None,
            sample_cache=None,
        ):
            option_probe_calls.append((decoder, codec, list(devices), set(encoder_names)))
            return {"cuda": [{"value": "0", "label": "0"}]}

        wrapper.probe_decoder_hardware_device_options = MethodType(fake_option_probe, wrapper)

        capabilities = wrapper.discover_capabilities(gpu_adapters=[{"vendor": "nvidia", "device_type": "discrete"}])

        profile = capabilities["decoderProfiles"][1]
        assert capabilities["hwaccels"] == ["cuda"]
        assert profile["name"] == "h264_cuvid"
        assert profile["hardwareDevices"] == ["cuda"]
        assert profile["hardwareDeviceOptions"] == {"cuda": [{"value": "0", "label": "0"}]}
        assert probe_calls == [("h264_cuvid", "h264", ["cuda", "qsv"], ["cuda", "qsv"], {"libx264"})]
        assert option_probe_calls == [("h264_cuvid", "h264", ["cuda"], {"libx264"})]

    def test_discover_capabilities_returns_only_verified_hwaccels(self):
        wrapper = FFmpegWrapper(ffmpeg_path="ffmpeg")

        wrapper.list_codec_names = MethodType(
            lambda self, mode: ["libx264"] if mode == "encoders" else ["h264_cuvid", "hevc_qsv"],
            wrapper,
        )
        wrapper.list_hwaccels = MethodType(lambda self: ["cuda", "qsv", "amf"], wrapper)
        wrapper.describe_codec = MethodType(
            lambda self, mode, name: f"""
Decoder {name}
    Supported hardware devices: {"cuda" if name == "h264_cuvid" else "qsv"}
""",
            wrapper,
        )
        wrapper.probe_decoder_hardware_devices = MethodType(
            lambda self, decoder, codec, candidates, hwaccels, encoder_names, probe_dir=None, sample_cache=None: [
                device for device in candidates if device == "cuda"
            ],
            wrapper,
        )
        wrapper.probe_decoder_hardware_device_options = MethodType(
            lambda self, decoder, codec, devices, encoder_names, probe_dir=None, sample_cache=None: {
                device: [{"value": "0", "label": "0"}] for device in devices
            },
            wrapper,
        )

        capabilities = wrapper.discover_capabilities(
            gpu_adapters=[
                {"vendor": "nvidia", "device_type": "discrete"},
                {"vendor": "intel", "device_type": "integrated"},
            ]
        )

        assert capabilities["hwaccels"] == ["cuda"]
