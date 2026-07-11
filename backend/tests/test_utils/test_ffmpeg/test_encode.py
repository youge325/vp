"""FFmpeg encode/decode argument builder tests."""

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
