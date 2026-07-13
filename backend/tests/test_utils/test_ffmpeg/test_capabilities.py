"""FFmpeg capability aggregation tests."""

from app.utils.ffmpeg import capabilities, capability_probe


def _install_probe_stubs(monkeypatch) -> None:
    monkeypatch.setattr(
        capability_probe,
        "list_codec_names",
        lambda _path, mode: ["hevc_nvenc", "h264_qsv", "libx264"] if mode == "encoders" else ["hevc_cuvid", "hevc_qsv"],
    )
    monkeypatch.setattr(capability_probe, "list_hwaccels", lambda _path: ["cuda", "qsv"])
    monkeypatch.setattr(
        capability_probe,
        "describe_codec",
        lambda _path, _mode, name: (
            "Supported pixel formats: yuv420p\n"
            f"Supported hardware devices: {'cuda' if 'cuvid' in name or 'nvenc' in name else 'qsv'}"
        ),
    )
    monkeypatch.setattr(
        capability_probe,
        "probe_rate_control_modes",
        lambda _path, _codec, _options: [{"mode": "bitrate", "defaultValue": 8}],
    )
    monkeypatch.setattr(
        capability_probe,
        "probe_decoder_hardware_capabilities",
        lambda _path, _decoder, _codec, devices, _hwaccels, _encoders, **_kwargs: (
            list(devices),
            {device: [{"value": "0", "label": "0"}] for device in devices},
        ),
    )


def test_discover_capabilities_filters_profiles_by_gpu_vendor(monkeypatch) -> None:
    _install_probe_stubs(monkeypatch)

    result = capabilities.discover_capabilities("ffmpeg", [{"name": "GPU", "vendor": "nvidia"}])

    assert result["hwaccels"] == ["cuda"]
    assert [profile["name"] for profile in result["encoderProfiles"]] == ["libx264", "hevc_nvenc"]
    assert [profile["name"] for profile in result["decoderProfiles"]] == ["software", "hevc_cuvid"]
    assert result["encoderProfiles"][0]["rateControlModes"] == [{"mode": "bitrate", "defaultValue": 8}]
    assert result["decoderProfiles"][1]["hardwareDevices"] == ["cuda"]
    assert result["decoderProfiles"][1]["hardwareDeviceOptions"] == {"cuda": [{"value": "0", "label": "0"}]}


def test_discover_capabilities_returns_only_verified_hwaccels(monkeypatch) -> None:
    _install_probe_stubs(monkeypatch)
    monkeypatch.setattr(
        capability_probe,
        "probe_decoder_hardware_capabilities",
        lambda _path, _decoder, _codec, devices, _hwaccels, _encoders, **_kwargs: (
            [device for device in devices if device == "cuda"],
            {"cuda": []} if "cuda" in devices else {},
        ),
    )

    result = capabilities.discover_capabilities(
        "ffmpeg",
        [{"name": "NVIDIA", "vendor": "nvidia"}, {"name": "Intel", "vendor": "intel"}],
    )

    assert result["hwaccels"] == ["cuda"]
