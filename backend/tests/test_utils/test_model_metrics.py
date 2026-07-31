from dataclasses import FrozenInstanceError
import operator
from pathlib import Path

import onnx
import pytest
from onnx import TensorProto, helper

from app.catalog.model_metrics import (
    MODEL_METRIC_SPECS_BY_ALGORITHM,
    PADDLEGAN_MODEL_METRIC_SPECS,
    RIFE_MODEL_METRIC_SPECS,
    ModelMetricSpec,
)
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.catalog.rife_models import SUPPORTED_MODELS
from app.cli.model_metric_projection import project_model_metrics
from app.utils.onnx_metric_analyzer import analyze_onnx_model


def _wire(spec):
    return project_model_metrics((spec,))[0].model_dump(by_alias=True, mode="json")


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

    detail = _wire(analyze_onnx_model(model_path, name="conv.onnx", label="Conv"))

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

    detail = _wire(analyze_onnx_model(model_path, name="dynamic.onnx"))

    assert detail["metrics"]["parameterCount"] == 224
    assert detail["metrics"]["gflopsPerMegapixel"] is None
    assert detail["metrics"]["activationBytesPerMegapixel"] is None
    assert detail["metrics"]["analysisStatus"] == "partial"
    assert detail["metrics"]["analysisNotes"]
    assert detail["metrics"]["engineMetrics"] == {}


def test_analyze_onnx_model_aggregates_repeated_graph_diagnostics(tmp_path: Path) -> None:
    model_path = tmp_path / "many-dynamic-convs.onnx"
    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, "height", "width"])
    output_info = helper.make_tensor_value_info("output-199", TensorProto.FLOAT, [1, 3, "height", "width"])
    nodes = []
    initializers = []
    previous = "input"
    for index in range(200):
        weight_name = f"weight-{index}"
        output_name = f"output-{index}"
        initializers.append(helper.make_tensor(weight_name, TensorProto.FLOAT, [3, 3, 1, 1], [0.1] * 9))
        nodes.append(helper.make_node("Conv", [previous, weight_name], [output_name]))
        previous = output_name
    graph = helper.make_graph(nodes, "many-dynamic-convs", [input_info], [output_info], initializers)
    onnx.save(helper.make_model(graph), model_path)

    detail = _wire(analyze_onnx_model(model_path))
    notes = detail["metrics"]["analysisNotes"]

    assert notes == [
        "Could not infer FLOPs for 200 Conv nodes.",
        "Could not infer activation shapes for 200 graph outputs.",
        "No static NCHW image input shape was found; resolution-scaled estimates are unavailable.",
    ]
    assert len(str(detail).encode("utf-8")) < 8_192


def test_metric_projection_bounds_external_diagnostics() -> None:
    spec = ModelMetricSpec(
        name="external.onnx",
        label="external.onnx",
        parameter_count=None,
        parameter_bytes=None,
        gflops_per_megapixel=None,
        activation_bytes_per_megapixel=None,
        runtime_overhead_bytes=None,
        runtime_frame_count=None,
        input_modulo=None,
        analysis_status="unknown",
        analysis_notes=tuple(f"diagnostic-{index}:" + "界" * 1_000 for index in range(100)),
    )

    detail = _wire(spec)
    notes = detail["metrics"]["analysisNotes"]

    assert len(notes) == 8
    assert all(len(note.encode("utf-8")) <= 512 for note in notes)
    assert all(note.endswith("… (diagnostic truncated)") for note in notes)


def test_analyze_onnx_model_returns_unknown_for_invalid_files(tmp_path: Path) -> None:
    model_path = tmp_path / "broken.onnx"
    model_path.write_bytes(b"not an onnx model")

    detail = _wire(analyze_onnx_model(model_path, name="broken.onnx"))

    assert detail["metrics"]["parameterCount"] is None
    assert detail["metrics"]["analysisStatus"] == "unknown"
    assert detail["metrics"]["analysisNotes"]


def test_builtin_rife_and_paddlegan_models_have_metric_details() -> None:
    rife_details = [_wire(detail) for detail in MODEL_METRIC_SPECS_BY_ALGORITHM["rife"]]
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

    ppmsvsr = _wire(PADDLEGAN_MODEL_METRIC_SPECS["ppmsvsr"])
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

    edvr = _wire(PADDLEGAN_MODEL_METRIC_SPECS["edvr"])
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
        detail = _wire(PADDLEGAN_MODEL_METRIC_SPECS[model_id])
        assert detail["metrics"]["parameterCount"] == parameter_count
        assert detail["metrics"]["runtimeOverheadBytes"]
        assert detail["metrics"]["activationBytesPerMegapixel"]
        assert detail["metrics"]["runtimeFrameCount"] is None
        assert detail["metrics"]["engineMetrics"]["tensorrt"]["runtimeOverheadBytes"] is not None
        assert detail["metrics"]["engineMetrics"]["tensorrt"]["activationBytesPerMegapixel"]


def test_builtin_metric_catalogs_are_immutable_and_match_model_catalogs() -> None:
    assert set(RIFE_MODEL_METRIC_SPECS) == set(SUPPORTED_MODELS)
    assert set(PADDLEGAN_MODEL_METRIC_SPECS) == set(PADDLEGAN_VSR_SPECS)

    with pytest.raises(TypeError):
        operator.setitem(RIFE_MODEL_METRIC_SPECS, "extra", RIFE_MODEL_METRIC_SPECS[SUPPORTED_MODELS[0]])
    with pytest.raises(FrozenInstanceError):
        setattr(PADDLEGAN_MODEL_METRIC_SPECS["edvr"], "label", "mutable")
