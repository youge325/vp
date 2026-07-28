"""Low-level FFmpeg codec capability probe tests."""

import subprocess
from pathlib import Path

from app.utils.ffmpeg import capability_probe


def test_parse_codec_profile_extracts_choice_number_and_boolean_options() -> None:
    profile = capability_probe.parse_codec_profile(
        {"name": "h264_nvenc", "label": "NVENC H.264", "family": "nvidia", "codec": "h264"},
        """
  -preset            <int>        E..V....... (from 0 to 18) (default p4)
     p1              1            fastest
     p4              4            medium
  -cq                <float>      E..V....... (from 0 to 51) (default 23)
  -forced-idr        <boolean>    E..V....... (default false)
""",
    )
    options = profile["options"]

    assert [option["name"] for option in options] == ["preset", "cq", "forced-idr"]
    assert options[0]["type"] == "choice"
    assert [choice["value"] for choice in options[0]["choices"]] == ["p1", "p4"]
    assert options[1]["defaultValue"] == 23.0
    assert options[2]["defaultValue"] is False


def test_parse_codec_profile_includes_pixel_format_option() -> None:
    profile = capability_probe.parse_codec_profile(
        {"name": "hevc_nvenc", "label": "NVENC H.265", "family": "nvidia", "codec": "hevc"},
        """
    Supported pixel formats: yuv420p nv12 p010le
    Supported hardware devices: cuda
  -preset            <int>        E..V....... (from 0 to 18) (default p4)
     p4              4            medium
""",
    )

    assert "pixelFormats" not in profile
    assert profile["hardwareDevices"] == ["cuda"]
    assert profile["options"][0]["name"] == "pix_fmt"
    assert [choice["value"] for choice in profile["options"][0]["choices"]] == [
        "yuv420p",
        "nv12",
        "p010le",
    ]


def test_probe_rate_control_modes_keeps_only_verified_modes(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        if "-cq" in command:
            raise RuntimeError("unsupported cq")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(capability_probe, "run_ffmpeg_command", fake_run)
    modes = capability_probe.probe_rate_control_modes(
        "ffmpeg",
        "h264_nvenc",
        [
            {"name": "cq", "defaultValue": 21},
            {"name": "qp", "defaultValue": 25},
        ],
    )

    assert [mode["mode"] for mode in modes] == ["qp", "bitrate"]
    assert ["-qp", "25"] in [calls[1][index : index + 2] for index in range(len(calls[1]) - 1)]
    assert ["-b:v", "8M"] in [calls[2][index : index + 2] for index in range(len(calls[2]) - 1)]


def test_probe_rate_control_modes_returns_empty_when_every_probe_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        capability_probe,
        "run_ffmpeg_command",
        lambda _command, **_kwargs: (_ for _ in ()).throw(RuntimeError("unsupported")),
    )

    assert capability_probe.probe_rate_control_modes("ffmpeg", "libx264", []) == []


def test_probe_decoder_hardware_capabilities_verifies_devices_and_options(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        if "-hwaccel" in command and command[command.index("-hwaccel") + 1] == "qsv":
            raise RuntimeError("qsv unavailable")
        if "-hwaccel_device" in command and command[command.index("-hwaccel_device") + 1] == "1":
            raise RuntimeError("device unavailable")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(capability_probe, "_DECODER_HARDWARE_DEVICE_PROBE_VALUES", ("0", "1"))
    monkeypatch.setattr(capability_probe, "run_ffmpeg_command", fake_run)
    devices, options = capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["cuda", "qsv", "cuda"],
        ["cuda", "qsv"],
        {"libx264"},
        probe_dir=str(tmp_path),
        sample_cache={},
    )

    assert devices == ["cuda"]
    assert options == {"cuda": [{"value": "0", "label": "0"}]}
    assert any("testsrc2=size=256x256:rate=1" in command for command in calls)


def test_probe_decoder_hardware_capabilities_returns_empty_without_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        capability_probe,
        "run_ffmpeg_command",
        lambda _command, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected probe")),
    )

    result = capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["qsv"],
        ["cuda"],
        {"libx264"},
    )

    assert result == ([], {})


def test_probe_decoder_hardware_capabilities_returns_empty_without_sample_encoder(tmp_path) -> None:
    result = capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["cuda"],
        ["cuda"],
        set(),
        probe_dir=str(tmp_path),
        sample_cache={},
    )

    assert result == ([], {})


def test_standalone_decoder_probe_owns_and_cleans_temporary_workspace(monkeypatch) -> None:
    sample_paths: list[Path] = []

    def fake_run(command: list[str], **_kwargs):
        if "testsrc2=size=256x256:rate=1" in command:
            sample_paths.append(Path(command[-1]))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(capability_probe, "_DECODER_HARDWARE_DEVICE_PROBE_VALUES", ("0", "1"))
    monkeypatch.setattr(capability_probe, "run_ffmpeg_command", fake_run)

    devices, options = capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["cuda"],
        ["cuda"],
        {"libx264"},
    )

    assert devices == ["cuda"]
    assert options == {"cuda": [{"value": "0", "label": "0"}, {"value": "1", "label": "1"}]}
    assert len(sample_paths) == 1
    assert not sample_paths[0].parent.exists()


def test_decoder_probe_reuses_shared_sample_cache(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(capability_probe, "_DECODER_HARDWARE_DEVICE_PROBE_VALUES", ("0",))
    monkeypatch.setattr(capability_probe, "run_ffmpeg_command", fake_run)
    cache: dict[str, str | None] = {}

    capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["cuda"],
        ["cuda"],
        {"libx264"},
        probe_dir=str(tmp_path),
        sample_cache=cache,
    )
    capability_probe.probe_decoder_hardware_capabilities(
        "ffmpeg",
        "h264_cuvid",
        "h264",
        ["cuda"],
        ["cuda"],
        {"libx264"},
        probe_dir=str(tmp_path),
        sample_cache=cache,
    )

    sample_generations = [command for command in calls if "testsrc2=size=256x256:rate=1" in command]
    assert len(sample_generations) == 1
