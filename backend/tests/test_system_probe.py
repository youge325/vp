"""System probe normalization tests."""

import json
import subprocess

import pytest

from app.utils import system_probe
from app.utils.system_probe import _classify_gpu_vendor, _is_virtual_gpu_adapter


def test_classify_gpu_vendor_uses_vendor_word_boundaries():
    assert _classify_gpu_vendor("NVIDIA GeForce RTX 3070") == "nvidia"
    assert _classify_gpu_vendor("Intel(R) UHD Graphics") == "intel"
    assert _classify_gpu_vendor("Advanced Micro Devices") == "amd"
    assert _classify_gpu_vendor("ATI Technologies Inc.") == "amd"
    assert _classify_gpu_vendor("Shanghai Best Oray Information Technology Co., Ltd.") == "other"
    assert _classify_gpu_vendor("Unknown Adapter") == "other"


@pytest.mark.parametrize(
    ("name", "compatibility", "pnp_device_id"),
    [
        ("Virtual Display Adapter", "Vendor", "PCI\\VEN_1234"),
        ("Remote Display Adapter", "Vendor", "PCI\\VEN_1234"),
        ("Mirror Driver", "Vendor", "PCI\\VEN_1234"),
        ("OrayIddDriver Device", "Oray", "PCI\\VEN_1234"),
        ("Display Adapter", "GameViewer", "PCI\\VEN_1234"),
        ("Display Adapter", "Vendor", "ROOT\\DISPLAY\\0000"),
        ("Display Adapter", "Vendor", "INDIRECTDSP\\VIRTUALDISPLAYDRIVER"),
    ],
)
def test_is_virtual_gpu_adapter_uses_name_compatibility_and_pnp_id(name, compatibility, pnp_device_id):
    assert _is_virtual_gpu_adapter(name, compatibility, pnp_device_id)


def test_is_virtual_gpu_adapter_keeps_unknown_physical_adapter():
    assert not _is_virtual_gpu_adapter("Acme Accelerator", "Acme", "PCI\\VEN_1234&DEV_5678")


def test_list_windows_gpu_adapters_filters_reported_virtual_displays(monkeypatch):
    rows = [
        {
            "Name": "OrayIddDriver Device",
            "AdapterCompatibility": "Shanghai Best Oray Information Technology Co., Ltd.",
            "PNPDeviceID": "ROOT\\DISPLAY\\0000",
        },
        {
            "Name": "GameViewer Virtual Display Adapter",
            "AdapterCompatibility": "GameViewer",
            "PNPDeviceID": "ROOT\\DISPLAY\\0001",
        },
        {
            "Name": "MuMu Virtual Display Adapter",
            "AdapterCompatibility": "MuMu",
            "PNPDeviceID": "ROOT\\DISPLAY\\0002",
        },
        {
            "Name": "Todesk Virtual Display Adapter",
            "AdapterCompatibility": "Hainan YouQu Info Tech",
            "PNPDeviceID": "ROOT\\DISPLAY\\0003",
        },
        {
            "Name": "NVIDIA GeForce RTX 3070 Laptop GPU",
            "AdapterCompatibility": "NVIDIA",
            "PNPDeviceID": "PCI\\VEN_10DE&DEV_24DD",
        },
        {
            "Name": "Honor Virtual Display Device",
            "AdapterCompatibility": "Honor",
            "PNPDeviceID": "INDIRECTDSP\\VIRTUALDISPLAYDRIVER",
        },
    ]
    monkeypatch.setattr(
        system_probe.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(rows),
            stderr="",
        ),
    )

    assert system_probe._list_windows_gpu_adapters() == [
        {
            "name": "NVIDIA GeForce RTX 3070 Laptop GPU",
            "vendor": "nvidia",
        }
    ]


def test_list_windows_gpu_adapters_keeps_duplicate_unknown_physical_adapters_and_skips_blank_names(monkeypatch):
    rows = [
        {
            "Name": "Acme Accelerator",
            "AdapterCompatibility": "Acme",
            "PNPDeviceID": "PCI\\VEN_1234&DEV_0001",
        },
        {
            "Name": "Acme Accelerator",
            "AdapterCompatibility": "Acme",
            "PNPDeviceID": "PCI\\VEN_1234&DEV_0002",
        },
        {
            "Name": " ",
            "AdapterCompatibility": "NVIDIA",
            "PNPDeviceID": "PCI\\VEN_10DE&DEV_0001",
        },
    ]
    monkeypatch.setattr(
        system_probe.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(rows),
            stderr="",
        ),
    )

    assert system_probe._list_windows_gpu_adapters() == [
        {"name": "Acme Accelerator", "vendor": "other"},
        {"name": "Acme Accelerator", "vendor": "other"},
    ]
