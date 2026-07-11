"""Aggregate low-level FFmpeg probes into application capability profiles."""

from __future__ import annotations

import tempfile
from typing import Any

from . import _constants
from . import capability_probe as _probe


def discover_capabilities(ffmpeg_path: str, gpu_adapters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    adapters = gpu_adapters or []
    available_vendors = {adapter.get("vendor") for adapter in adapters}
    encoder_names = set(_probe.list_codec_names(ffmpeg_path, "encoders"))
    decoder_names = set(_probe.list_codec_names(ffmpeg_path, "decoders"))
    hwaccels = _probe.list_hwaccels(ffmpeg_path)

    encoder_profiles: list[dict[str, Any]] = []
    for candidate in _constants.ENCODER_CANDIDATES:
        if candidate["name"] not in encoder_names:
            continue
        if candidate["family"] != "cpu" and candidate["family"] not in available_vendors:
            continue
        profile = _probe.parse_codec_profile(
            candidate,
            _probe.describe_codec(ffmpeg_path, "encoder", candidate["name"]),
        )
        profile["rateControlModes"] = _probe.probe_rate_control_modes(ffmpeg_path, profile["name"], profile["options"])
        encoder_profiles.append(profile)

    decoder_profiles: list[dict[str, Any]] = [
        {
            "name": "software",
            "label": "Software Decode",
            "family": "software",
            "codec": "any",
            "available": True,
            "hardwareDevices": [],
            "hardwareDeviceOptions": {},
            "options": [],
        }
    ]
    verified_hwaccels: list[str] = []
    decoder_sample_cache: dict[str, str | None] = {}
    with tempfile.TemporaryDirectory(prefix="vp-decoder-probe-") as decoder_probe_dir:
        for candidate in _constants.DECODER_CANDIDATES:
            if candidate["name"] not in decoder_names or candidate["family"] not in available_vendors:
                continue
            profile = _probe.parse_codec_profile(
                candidate,
                _probe.describe_codec(ffmpeg_path, "decoder", candidate["name"]),
            )
            profile["hardwareDevices"] = _probe.probe_decoder_hardware_devices(
                ffmpeg_path,
                profile["name"],
                profile["codec"],
                profile["hardwareDevices"],
                hwaccels,
                encoder_names,
                probe_dir=decoder_probe_dir,
                sample_cache=decoder_sample_cache,
            )
            for device in profile["hardwareDevices"]:
                if device not in verified_hwaccels:
                    verified_hwaccels.append(device)
            profile["hardwareDeviceOptions"] = _probe.probe_decoder_hardware_device_options(
                ffmpeg_path,
                profile["name"],
                profile["codec"],
                profile["hardwareDevices"],
                encoder_names,
                probe_dir=decoder_probe_dir,
                sample_cache=decoder_sample_cache,
            )
            decoder_profiles.append(profile)

    return {
        "hwaccels": verified_hwaccels,
        "encoderProfiles": encoder_profiles,
        "decoderProfiles": decoder_profiles,
    }
