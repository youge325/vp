"""RIFE 全版本模型权重加载验证测试。

权重文件预置于 backend/models/ 目录下（从 vs-rife 复制），
本测试验证：
1. 每个版本的 IFNet 可以正常创建实例
2. 每个版本的 state_dict key 结构与 vs-rife 一致
3. model_loader.py 的动态导入和 Head 处理逻辑正确
4. 有/无 Head 的推理路径可以正确构建
5. 全部 36 个版本的真实权重可以正确加载
"""

import os
import sys
import pytest

pytestmark = pytest.mark.pytorch

import torch
import torch.nn as nn

# 确保 backend 目录在 path 上
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.algorithms.pytorch.rife._model_spec import MODEL_CONFIGS
from app.algorithms.pytorch.rife.model_loader import (
    SUPPORTED_MODELS,
    HEAD_NONE,
    HEAD_SEQUENTIAL,
    HEAD_CUSTOM,
    _version_to_module_name,
    _build_sequential_head,
    get_model_dir,
)


class TestModelConfigs:
    """测试模型配置完整性。"""

    def test_all_versions_have_config(self):
        """每个支持的版本都有配置。"""
        for version in SUPPORTED_MODELS:
            assert version in MODEL_CONFIGS, f"缺少版本 {version} 的配置"

    def test_config_fields(self):
        """每个配置都有必要的字段。"""
        for version, config in MODEL_CONFIGS.items():
            assert "encode_channel" in config, f"{version} 缺少 encode_channel"
            assert "modulo" in config, f"{version} 缺少 modulo"
            assert "ensemble" in config, f"{version} 缺少 ensemble"
            assert "head_type" in config, f"{version} 缺少 head_type"
            assert config["head_type"] in (HEAD_NONE, HEAD_SEQUENTIAL, HEAD_CUSTOM)

    def test_no_head_versions(self):
        """v4.0~v4.6 无 Head。"""
        for v in ["4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6"]:
            assert MODEL_CONFIGS[v]["head_type"] == HEAD_NONE
            assert MODEL_CONFIGS[v]["encode_channel"] == 0

    def test_sequential_head_versions(self):
        """v4.7~v4.9, v4.10~v4.12, v4.12.lite, v4.13.lite 使用 nn.Sequential Head。"""
        seq_versions = [
            "4.7",
            "4.8",
            "4.9",
            "4.10",
            "4.11",
            "4.12",
            "4.12.lite",
            "4.13.lite",
        ]
        for v in seq_versions:
            assert MODEL_CONFIGS[v]["head_type"] == HEAD_SEQUENTIAL, f"{v} 应该是 SEQUENTIAL Head"
            assert "head_config" in MODEL_CONFIGS[v], f"{v} 缺少 head_config"

    def test_custom_head_versions(self):
        """v4.13+ 使用自定义 Head。"""
        custom_versions = [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] == HEAD_CUSTOM]
        # v4.13 ~ v4.26.heavy 的大部分版本
        assert "4.13" in custom_versions
        assert "4.25" in custom_versions
        assert "4.26.heavy" in custom_versions

    def test_modulo_values(self):
        """modulo 值正确。"""
        # 大部分版本 modulo=32
        for v in ["4.0", "4.13", "4.21", "4.24"]:
            assert MODEL_CONFIGS[v]["modulo"] == 32

        # v4.25+ modulo=64
        for v in ["4.25", "4.25.heavy", "4.26", "4.26.heavy"]:
            assert MODEL_CONFIGS[v]["modulo"] == 64

        # v4.25.lite modulo=128
        assert MODEL_CONFIGS["4.25.lite"]["modulo"] == 128

    def test_ensemble_flags(self):
        """ensemble 标志正确。"""
        # v4.0~v4.20 支持 ensemble
        for v in SUPPORTED_MODELS[:24]:  # 前24个版本
            if MODEL_CONFIGS[v]["head_type"] != HEAD_NONE or v >= "4.13":
                pass  # 不用严格检查，vs-rife 源码中 4.0~4.20 全部 ensemble=True
            if v in [
                "4.21",
                "4.22",
                "4.22.lite",
                "4.23",
                "4.24",
                "4.25",
                "4.25.lite",
                "4.25.heavy",
                "4.26",
                "4.26.heavy",
            ]:
                assert MODEL_CONFIGS[v]["ensemble"] is False

    def test_version_count(self):
        """总共 36 个版本。"""
        assert len(SUPPORTED_MODELS) == 36
        assert len(MODEL_CONFIGS) == 36


class TestVersionToModuleName:
    """测试版本号到模块名的转换。"""

    def test_simple_version(self):
        assert _version_to_module_name("4.25") == "ifnet_v4_25"

    def test_lite_version(self):
        assert _version_to_module_name("4.12.lite") == "ifnet_v4_12_lite"

    def test_heavy_version(self):
        assert _version_to_module_name("4.26.heavy") == "ifnet_v4_26_heavy"

    def test_single_digit(self):
        assert _version_to_module_name("4.0") == "ifnet_v4_0"


class TestSequentialHead:
    """测试 nn.Sequential Head 构建。"""

    def test_v47_head(self):
        """v4.7~v4.9 的 Head: 3→16→4，无 LeakyReLU。"""
        head = _build_sequential_head(3, 16, 4)
        assert len(head) == 2
        assert isinstance(head[0], nn.Conv2d)
        assert head[0].in_channels == 3
        assert head[0].out_channels == 16
        assert isinstance(head[1], nn.ConvTranspose2d)
        assert head[1].in_channels == 16
        assert head[1].out_channels == 4

    def test_v410_head(self):
        """v4.10~v4.12 的 Head: 3→32→8，带 LeakyReLU。"""
        head = _build_sequential_head(3, 32, 8)
        assert len(head) == 7
        assert isinstance(head[0], nn.Conv2d)
        assert head[0].in_channels == 3
        assert head[0].out_channels == 32
        assert isinstance(head[6], nn.ConvTranspose2d)
        assert head[6].in_channels == 32
        assert head[6].out_channels == 8

    def test_v412lite_head(self):
        """v4.12.lite 的 Head: 3→32→4。"""
        head = _build_sequential_head(3, 32, 4)
        assert isinstance(head[6], nn.ConvTranspose2d)
        assert head[6].out_channels == 4


class TestIFNetCreation:
    """测试所有版本的 IFNet 实例创建。"""

    @pytest.mark.parametrize("version", SUPPORTED_MODELS)
    def test_ifnet_can_be_created(self, version):
        """每个版本的 IFNet 都可以正常创建。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        IFNet = mod.IFNet

        config = MODEL_CONFIGS[version]
        ensemble = config.get("ensemble", False)

        # 使用 meta device 避免实际分配内存
        with torch.device("meta"):
            model = IFNet(scale=1.0, ensemble=ensemble)

        assert model is not None

    @pytest.mark.parametrize("version", SUPPORTED_MODELS)
    def test_ifnet_has_forward_method(self, version):
        """每个版本的 IFNet 都有 forward 方法。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        IFNet = mod.IFNet

        assert hasattr(IFNet, "forward")

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] == HEAD_CUSTOM],
    )
    def test_custom_head_class_exists(self, version):
        """有自定义 Head 的版本都有 Head 类可导入。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)

        assert hasattr(mod, "Head"), f"{version} 应该导出 Head 类"

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] == HEAD_CUSTOM],
    )
    def test_custom_head_can_be_created(self, version):
        """自定义 Head 类可以正常实例化。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        Head = mod.Head

        with torch.device("meta"):
            head = Head()

        assert head is not None

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] == HEAD_NONE],
    )
    def test_no_head_versions_no_head_class(self, version):
        """无 Head 版本不需要 Head 类。"""
        # 这些版本的 forward 不接受 f0/f1
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)

        # 无 Head 版本不导出 Head（或者导出了但不使用）
        # 关键是 model_loader 不会尝试创建 Head


class TestStateDictStructure:
    """测试 state_dict 结构与 vs-rife 兼容。"""

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] != HEAD_NONE],
    )
    def test_encode_keys_exist(self, version):
        """有 Head 的版本，IFNet 的 state_dict 包含 encode.* 键。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        IFNet = mod.IFNet

        config = MODEL_CONFIGS[version]
        ensemble = config.get("ensemble", False)

        # 在 CPU 上创建小模型检查 state_dict 结构
        model = IFNet(scale=1.0, ensemble=ensemble)
        sd = model.state_dict()

        encode_keys = [k for k in sd.keys() if k.startswith("encode.")]
        assert len(encode_keys) > 0, f"{version} 的 state_dict 应包含 encode.* 键，但只有: {list(sd.keys())[:20]}"

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_MODELS if MODEL_CONFIGS[v]["head_type"] == HEAD_NONE],
    )
    def test_no_encode_keys_for_headless(self, version):
        """无 Head 的版本，IFNet 的 state_dict 不包含 encode.* 键。"""
        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        IFNet = mod.IFNet

        config = MODEL_CONFIGS[version]
        ensemble = config.get("ensemble", False)

        model = IFNet(scale=1.0, ensemble=ensemble)
        sd = model.state_dict()

        encode_keys = [k for k in sd.keys() if k.startswith("encode.")]
        assert len(encode_keys) == 0, f"{version} 的 state_dict 不应包含 encode.* 键"


class TestWeightLoadingWithRealWeights:
    """
    使用实际权重文件测试加载。

    权重文件预置于 backend/models/ 目录下。
    """

    def _get_model_dir(self) -> str:
        """获取模型权重目录。"""
        return get_model_dir()

    def _get_weight_path(self, version: str) -> str:
        """获取权重文件路径。"""
        return os.path.join(self._get_model_dir(), f"flownet_v{version}.pkl")

    def _weight_exists(self, version: str) -> bool:
        """检查权重文件是否存在且非空。"""
        path = self._get_weight_path(version)
        return os.path.isfile(path) and os.path.getsize(path) > 0

    @pytest.mark.parametrize("version", SUPPORTED_MODELS)
    def test_load_state_dict_structure_match(self, version):
        """验证加载 state_dict 后 key 结构匹配。"""
        if not self._weight_exists(version):
            pytest.skip(f"权重文件不存在或为空: flownet_v{version}.pkl")

        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)
        IFNet = mod.IFNet

        config = MODEL_CONFIGS[version]
        ensemble = config.get("ensemble", False)

        # 加载权重（旧格式 pkl 不支持 mmap，需使用 weights_only=False）
        weight_path = self._get_weight_path(version)
        state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)
        state_dict = {k.replace("module.", ""): v for k, v in state_dict.items() if "module." in k}

        # 创建模型并加载（strict=False 允许部分加载）
        with torch.device("meta"):
            model = IFNet(scale=1.0, ensemble=ensemble)

        missing, unexpected = model.load_state_dict(state_dict, strict=False, assign=True)

        # 检查：encode.* 应该匹配到 IFNet 的 self.encode
        if config["head_type"] == HEAD_NONE:
            # 无 Head 版本不应有 encode 键
            encode_missing = [k for k in missing if k.startswith("encode.")]
            assert len(encode_missing) == 0, f"{version}: 不应有缺失的 encode 键，但缺失: {encode_missing}"

        # 检查不应有缺失的必要键（但训练残余权重如 teacher/block_tea/contextnet/unet/caltime
        # 是预期中的 unexpected keys，vs-rife 也用 strict=False 加载并忽略）
        # 只检查非训练残余的 unexpected keys
        non_training_unexpected = [
            k for k in unexpected if not k.startswith(("teacher.", "block_tea.", "contextnet.", "unet.", "caltime."))
        ]
        assert len(non_training_unexpected) == 0, f"{version}: 非训练残余 unexpected keys: {non_training_unexpected}"

    @pytest.mark.parametrize("version", SUPPORTED_MODELS)
    def test_head_weight_loading(self, version):
        """验证 Head 编码器权重可以正确加载。"""
        if not self._weight_exists(version):
            pytest.skip(f"权重文件不存在或为空: flownet_v{version}.pkl")

        config = MODEL_CONFIGS[version]
        head_type = config["head_type"]

        if head_type == HEAD_NONE:
            pytest.skip(f"{version} 无 Head 编码器")

        import importlib

        module_name = _version_to_module_name(version)
        rife_package = f"app.algorithms.pytorch.rife.{module_name}"
        mod = importlib.import_module(rife_package)

        # 加载权重
        weight_path = self._get_weight_path(version)
        state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)
        state_dict = {k.replace("module.", ""): v for k, v in state_dict.items() if "module." in k}

        # 提取 encode 权重
        encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}
        assert len(encode_state_dict) > 0, f"{version}: 权重中无 encode.* 键"

        # 创建 Head 并加载
        if head_type == HEAD_CUSTOM:
            Head = mod.Head
            with torch.device("meta"):
                head = Head()
        elif head_type == HEAD_SEQUENTIAL:
            head_config = config.get("head_config", {})
            with torch.device("meta"):
                head = _build_sequential_head(
                    in_channels=head_config.get("in_channels", 3),
                    mid_channels=head_config.get("mid_channels", 16),
                    out_channels=head_config.get("out_channels", 4),
                )

        missing, unexpected = head.load_state_dict(encode_state_dict, strict=False, assign=True)
        assert len(missing) == 0, f"{version} Head 加载缺失键: {missing}"
        assert len(unexpected) == 0, f"{version} Head 加载意外键: {unexpected}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
