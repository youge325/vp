from pathlib import Path

import onnx
import pytest
from onnx import TensorProto, helper

from app.algorithms.pytorch.rife._model_spec import SUPPORTED_MODELS
from app.utils.model_metrics import (
    analyze_onnx_model,
    get_paddlegan_model_detail,
    get_rife_model_details,
)


def _save_conv_model(path: Path, *, dynamic: bool = False) -> None:
    height = "height" if dynamic else 8
    width = "width" if dynamic else 8
    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, height, width])
    output_info = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 8, height, width])
    weight = helper.make_tensor(
        "weight",
        TensorProto.FLOAT,
        [8, 3, 3, 3],
        [0.1] * (8 * 3 * 3 * 3),
    )
    bias = helper.make_tensor("bias", TensorProto.FLOAT, [8], [0.0] * 8)
    node = helper.make_node(
        "Conv",
        ["input", "weight", "bias"],
        ["output"],
        kernel_shape=[3, 3],
        pads=[1, 1, 1, 1],
    )
    graph = helper.make_graph([node], "conv-model", [input_info], [output_info], [weight, bias])
    onnx.save(helper.make_model(graph), path)


def test_analyze_onnx_model_counts_parameters_and_estimates_conv_flops(tmp_path: Path) -> None:
    model_path = tmp_path / "conv.onnx"
    _save_conv_model(model_path)

    detail = analyze_onnx_model(model_path, name="conv.onnx", label="Conv")

    assert detail["name"] == "conv.onnx"
    assert detail["label"] == "Conv"
    assert detail["metrics"]["parameterCount"] == 224
    assert detail["metrics"]["parameterBytes"] == 896
    assert detail["metrics"]["gflopsPerMegapixel"] == pytest.approx(0.432)
    assert detail["metrics"]["activationBytesPerMegapixel"] is not None
    assert detail["metrics"]["analysisStatus"] == "ok"
    assert detail["metrics"]["analysisNotes"] == []
    assert detail["metrics"]["engineMetrics"] == {}


def test_analyze_onnx_model_keeps_parameters_when_dynamic_shapes_hide_flops(tmp_path: Path) -> None:
    model_path = tmp_path / "dynamic.onnx"
    _save_conv_model(model_path, dynamic=True)

    detail = analyze_onnx_model(model_path, name="dynamic.onnx")

    assert detail["metrics"]["parameterCount"] == 224
    assert detail["metrics"]["gflopsPerMegapixel"] is None
    assert detail["metrics"]["activationBytesPerMegapixel"] is None
    assert detail["metrics"]["analysisStatus"] == "partial"
    assert detail["metrics"]["analysisNotes"]
    assert detail["metrics"]["engineMetrics"] == {}


def test_analyze_onnx_model_returns_unknown_for_invalid_files(tmp_path: Path) -> None:
    model_path = tmp_path / "broken.onnx"
    model_path.write_bytes(b"not an onnx model")

    detail = analyze_onnx_model(model_path, name="broken.onnx")

    assert detail["metrics"]["parameterCount"] is None
    assert detail["metrics"]["analysisStatus"] == "unknown"
    assert detail["metrics"]["analysisNotes"]


def test_builtin_rife_and_paddlegan_models_have_metric_details() -> None:
    rife_details = get_rife_model_details()
    assert [detail["name"] for detail in rife_details] == list(SUPPORTED_MODELS)
    assert all(detail["metrics"]["parameterCount"] for detail in rife_details)
    assert all(detail["metrics"]["inputModulo"] for detail in rife_details)

    rife_425 = next(detail for detail in rife_details if detail["name"] == "4.25")
    assert rife_425["metrics"]["parameterCount"] == 5_670_892
    assert rife_425["metrics"]["runtimeOverheadBytes"] == pytest.approx(38_000_000, rel=0.02)
    assert rife_425["metrics"]["activationBytesPerMegapixel"] == pytest.approx(694_800_000, rel=0.01)
    rife_425_trt = rife_425["metrics"]["engineMetrics"]["tensorrt"]
    assert rife_425_trt["runtimeOverheadBytes"] is not None
    assert rife_425_trt["activationBytesPerMegapixel"] is not None
    assert rife_425_trt["gflopsPerMegapixel"] == rife_425["metrics"]["gflopsPerMegapixel"]

    ppmsvsr = get_paddlegan_model_detail("ppmsvsr")
    assert ppmsvsr["name"] == "x4"
    assert ppmsvsr["label"] == "PP-MSVSR"
    assert ppmsvsr["metrics"]["parameterCount"] == 1_453_607
    assert ppmsvsr["metrics"]["parameterBytes"] == 5_814_428
    assert ppmsvsr["metrics"]["runtimeOverheadBytes"] is not None
    assert ppmsvsr["metrics"]["runtimeFrameCount"] is None
    assert ppmsvsr["metrics"]["runtimeOverheadBytes"] == pytest.approx(2_391_117_604, rel=0.001)
    assert ppmsvsr["metrics"]["activationBytesPerMegapixel"] == pytest.approx(1_981_031_424, rel=0.001)
    assert ppmsvsr["metrics"]["gflopsPerMegapixel"] is not None
    ppmsvsr_trt = ppmsvsr["metrics"]["engineMetrics"]["tensorrt"]
    assert ppmsvsr_trt["runtimeOverheadBytes"] is not None
    assert ppmsvsr_trt["activationBytesPerMegapixel"] is not None
    assert ppmsvsr_trt["gflopsPerMegapixel"] == ppmsvsr["metrics"]["gflopsPerMegapixel"]

    edvr = get_paddlegan_model_detail("edvr")
    assert edvr["metrics"]["parameterCount"] == 20_633_827
    assert edvr["metrics"]["runtimeOverheadBytes"] is not None
    assert edvr["metrics"]["runtimeFrameCount"] == 5
    assert edvr["metrics"]["runtimeOverheadBytes"] == pytest.approx(84_074_752, rel=0.001)
    assert edvr["metrics"]["activationBytesPerMegapixel"] == pytest.approx(7_300_784_570, rel=0.001)
    assert edvr["metrics"]["engineMetrics"]["tensorrt"]["runtimeFrameCount"] == 5

    for model_id, parameter_count in {
        "ppmsvsr-large": 7_417_197,
        "basicvsr": 6_291_311,
        "iconvsr": 8_694_991,
        "basicvsr-plus-plus": 7_322_927,
    }.items():
        detail = get_paddlegan_model_detail(model_id)
        assert detail["metrics"]["parameterCount"] == parameter_count
        assert detail["metrics"]["runtimeOverheadBytes"]
        assert detail["metrics"]["activationBytesPerMegapixel"]
        assert detail["metrics"]["runtimeFrameCount"] is None
        assert detail["metrics"]["engineMetrics"]["tensorrt"]["runtimeOverheadBytes"] is not None
        assert detail["metrics"]["engineMetrics"]["tensorrt"]["activationBytesPerMegapixel"]
