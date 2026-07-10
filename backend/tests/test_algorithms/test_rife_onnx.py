"""RIFE ONNX 导出与推理验证测试。

验证：
1. RIFE v4.25 可以正确导出为 ONNX
2. ONNX 模型与 PyTorch 模型输出数值接近
3. ONNX Backend 可以完成一轮完整插值推理
"""

import os
import sys

import numpy as np
import pytest

pytestmark = pytest.mark.pytorch

# 确保 backend 目录在 path 上
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _is_torch_available():
    try:
        import torch

        return True
    except ImportError:
        return False


def _is_onnxruntime_available():
    try:
        import onnxruntime

        return True
    except ImportError:
        return False


def _weight_exists(version: str) -> bool:
    from app.algorithms.pytorch.rife.model_loader import get_model_dir

    path = os.path.join(get_model_dir(), f"flownet_v{version}.pkl")
    return os.path.isfile(path) and os.path.getsize(path) > 0


@pytest.mark.skipif(not _is_torch_available(), reason="PyTorch 未安装")
@pytest.mark.skipif(not _is_onnxruntime_available(), reason="onnxruntime 未安装")
@pytest.mark.skipif(not _weight_exists("4.25"), reason="RIFE v4.25 权重不存在")
class TestRIFEONNXExport:
    """测试 RIFE ONNX 导出。"""

    @pytest.fixture(scope="class")
    def onnx_path(self, tmp_path_factory):
        """导出 ONNX 模型并返回路径（类级别只执行一次）。"""
        from app.algorithms.pytorch.rife.onnx_export import export_rife_to_onnx

        output_dir = tmp_path_factory.mktemp("onnx_models")
        onnx_path = os.path.join(output_dir, "rife_v4.25.onnx")
        export_rife_to_onnx(
            model_version="4.25",
            output_path=onnx_path,
            dummy_size=(256, 256),
        )
        assert os.path.isfile(onnx_path)
        return onnx_path

    def test_onnx_file_created(self, onnx_path):
        assert os.path.getsize(onnx_path) > 0

    def test_onnx_inference_runs(self, onnx_path):
        """ONNX 模型可以加载并运行推理。"""
        import onnxruntime as ort

        session = ort.InferenceSession(onnx_path)
        h, w = 256, 256
        img0 = np.random.rand(1, 3, h, w).astype(np.float32)
        img1 = np.random.rand(1, 3, h, w).astype(np.float32)
        timestep = np.full((1, 1, h, w), 0.5, dtype=np.float32)
        flow_div = np.array([(w - 1.0) / 2.0, (h - 1.0) / 2.0], dtype=np.float32)
        grid = np.zeros((1, 2, h, w), dtype=np.float32)  # dummy grid, values don't matter for shape test

        feed = {
            "img0": img0,
            "img1": img1,
            "timestep": timestep,
            "tenFlow_div": flow_div,
            "backwarp_tenGrid": grid,
        }
        # 过滤模型实际需要的输入
        input_names = {inp.name for inp in session.get_inputs()}
        feed = {k: v for k, v in feed.items() if k in input_names}

        outputs = session.run(None, feed)
        assert len(outputs) == 1
        assert outputs[0].shape == (1, 3, h, w)

    def test_onnx_vs_pytorch_consistency(self, onnx_path):
        """ONNX 输出与 PyTorch 输出数值接近（使用 padding 到 modulo 倍数的尺寸）。"""
        import torch
        import onnxruntime as ort

        from app.algorithms.pytorch.rife._model_spec import MODEL_CONFIGS
        from app.algorithms.pytorch.rife.model_loader import create_backwarp_grid, create_flow_div, load_rife_model

        # 加载 PyTorch 模型
        flownet, encode, config = load_rife_model(model_version="4.25", device="cpu", fp16=False)
        flownet.eval()

        # 使用非 256 的原始尺寸，验证 padding 后 ONNX 与 PyTorch 一致
        orig_h, orig_w = 240, 360
        modulo = MODEL_CONFIGS["4.25"]["modulo"]
        pad_h = ((orig_h - 1) // modulo + 1) * modulo
        pad_w = ((orig_w - 1) // modulo + 1) * modulo
        h, w = pad_h, pad_w

        img0 = torch.rand(1, 3, h, w)
        img1 = torch.rand(1, 3, h, w)
        timestep = torch.full((1, 1, h, w), 0.5)
        flow_div = create_flow_div(h, w, torch.device("cpu"))
        grid = create_backwarp_grid(h, w, torch.device("cpu"))

        with torch.no_grad():
            f0 = encode(img0)
            f1 = encode(img1)
            pytorch_out = flownet(img0, img1, timestep, flow_div, grid, f0, f1).numpy()

        # ONNX 推理
        session = ort.InferenceSession(onnx_path)
        feed = {
            "img0": img0.numpy(),
            "img1": img1.numpy(),
            "timestep": timestep.numpy(),
            "tenFlow_div": flow_div.numpy(),
            "backwarp_tenGrid": grid.numpy(),
        }
        input_names = {inp.name for inp in session.get_inputs()}
        feed = {k: v for k, v in feed.items() if k in input_names}
        onnx_out = session.run(None, feed)[0]

        # 允许一定数值误差（ONNX Runtime 与 PyTorch 实现差异：Resize/GridSample/Conv 等存在平台差异）
        np.testing.assert_allclose(pytorch_out, onnx_out, rtol=5e-2, atol=2e-2)

    def test_onnx_dynamic_shape(self, onnx_path):
        """ONNX 模型支持动态尺寸（使用 modulo 倍数尺寸验证）。"""
        import onnxruntime as ort
        from app.algorithms.pytorch.rife._model_spec import MODEL_CONFIGS

        session = ort.InferenceSession(onnx_path)
        modulo = MODEL_CONFIGS["4.25"]["modulo"]
        # 使用非 256 但为 modulo 倍数的尺寸
        h, w = modulo * 3, modulo * 5  # 192 x 320
        img0 = np.random.rand(1, 3, h, w).astype(np.float32)
        img1 = np.random.rand(1, 3, h, w).astype(np.float32)
        timestep = np.full((1, 1, h, w), 0.5, dtype=np.float32)
        flow_div = np.array([(w - 1.0) / 2.0, (h - 1.0) / 2.0], dtype=np.float32)
        grid = np.zeros((1, 2, h, w), dtype=np.float32)

        feed = {
            "img0": img0,
            "img1": img1,
            "timestep": timestep,
            "tenFlow_div": flow_div,
            "backwarp_tenGrid": grid,
        }
        input_names = {inp.name for inp in session.get_inputs()}
        feed = {k: v for k, v in feed.items() if k in input_names}

        outputs = session.run(None, feed)
        assert outputs[0].shape == (1, 3, h, w)


@pytest.mark.skipif(not _is_onnxruntime_available(), reason="onnxruntime 未安装")
@pytest.mark.skipif(not _weight_exists("4.25"), reason="RIFE v4.25 权重不存在")
class TestRIFEONNXSolver:
    """测试 RIFEONNXSolver 端到端推理。"""

    @pytest.fixture(scope="class")
    def solver(self, tmp_path_factory):
        """导出 ONNX 并创建 Solver。"""
        from app.algorithms.pytorch.rife.onnx_export import export_rife_to_onnx
        from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver
        from app.algorithms.pytorch.rife.model_loader import get_model_dir

        # 导出到 models 目录（solver 默认从这里加载）
        model_dir = get_model_dir()
        onnx_path = os.path.join(model_dir, "interpolation", "rife", "rife_v4.25.onnx")
        if not os.path.isfile(onnx_path):
            export_rife_to_onnx(
                model_version="4.25",
                output_path=onnx_path,
                dummy_size=(256, 256),
            )
        return RIFEONNXSolver(model_version="4.25", model_dir=model_dir)

    def test_interpolate_shape(self, solver):
        """插值输出形状正确。"""
        h, w = 240, 360
        img0 = np.random.rand(1, 3, h, w).astype(np.float32)
        img1 = np.random.rand(1, 3, h, w).astype(np.float32)
        mid = solver.interpolate(img0, img1, timestep=0.5)
        assert mid.shape == (1, 3, h, w)
        assert mid.dtype == np.float32
        assert mid.min() >= 0.0
        assert mid.max() <= 1.0

    def test_interpolate_multi(self, solver):
        """多倍插值返回正确数量的中间帧。"""
        h, w = 120, 160
        img0 = np.random.rand(1, 3, h, w).astype(np.float32)
        img1 = np.random.rand(1, 3, h, w).astype(np.float32)
        mids = solver.interpolate_multi(img0, img1, multi=4)
        assert len(mids) == 3
        for mid in mids:
            assert mid.shape == (1, 3, h, w)


@pytest.mark.skipif(not _is_onnxruntime_available(), reason="onnxruntime 未安装")
@pytest.mark.skipif(not _weight_exists("4.25"), reason="RIFE v4.25 权重不存在")
class TestFrameInterpolationAlgorithmONNX:
    """测试 FrameInterpolationAlgorithm + OnnxBackend 端到端。"""

    @pytest.fixture(scope="class")
    def algorithm(self, tmp_path_factory):
        """导出 ONNX 并创建算法实例。"""
        from app.algorithms.pytorch.rife.onnx_export import export_rife_to_onnx
        from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver
        from app.algorithms.pytorch.rife.model_loader import get_model_dir
        from app.algorithms.tensor_backend import OnnxBackend
        from app.processing.interpolation import FrameInterpolationAlgorithm

        model_dir = get_model_dir()
        onnx_path = os.path.join(model_dir, "interpolation", "rife", "rife_v4.25.onnx")
        if not os.path.isfile(onnx_path):
            export_rife_to_onnx(
                model_version="4.25",
                output_path=onnx_path,
                dummy_size=(256, 256),
            )

        backend = OnnxBackend()
        algo = FrameInterpolationAlgorithm(
            tensor_backend=backend,
            model_version="4.25",
        )
        return algo, backend

    def test_process_frame_pair(self, algorithm):
        """跑一轮 onnx 后端插值验证。"""
        algo, backend = algorithm
        h, w = 180, 320
        frame0 = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        frame1 = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)

        # tensor backend 转换
        t0 = backend.numpy_to_tensor(frame0)
        t1 = backend.numpy_to_tensor(frame1)

        # 插值
        result = algo.process_frame_pair(t0, t1, timestep=0.5)

        # 转回 numpy
        result_np = backend.tensor_to_numpy(result)

        assert result_np.shape == (h, w, 3)
        assert result_np.dtype == np.uint8
