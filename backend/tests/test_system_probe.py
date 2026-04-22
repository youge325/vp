"""System probe normalization tests."""

from app.utils.system_probe import classify_gpu_device_type, classify_gpu_vendor


def test_classify_gpu_vendor_normalizes_common_vendors():
    assert classify_gpu_vendor("NVIDIA GeForce RTX 3070") == "nvidia"
    assert classify_gpu_vendor("Intel(R) UHD Graphics") == "intel"
    assert classify_gpu_vendor("Advanced Micro Devices") == "amd"
    assert classify_gpu_vendor("Unknown Adapter") == "other"


def test_classify_gpu_device_type_detects_virtual_and_integrated():
    assert classify_gpu_device_type("Intel(R) UHD Graphics", "intel") == "integrated"
    assert classify_gpu_device_type("NVIDIA GeForce RTX 3070", "nvidia") == "discrete"
    assert classify_gpu_device_type("Microsoft Remote Display Adapter", "other") == "virtual"
