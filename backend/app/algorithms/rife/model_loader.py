"""RIFE 模型加载器 — 权重加载、设备管理。

支持：
- 36 个 RIFE 模型版本（v4.0 ~ v4.26.heavy）
- 从本地路径加载权重（权重文件预置于 backend/models/ 目录）
- GPU/CPU 设备管理
- fp16 半精度推理
- 根据 Head 类型自动分离加载编码器

参考 vs-rife 的 init_module 逻辑：
- v4.0~v4.6: 无 Head 编码器，IFNet.forward 不接受 f0/f1
- v4.7~v4.9: nn.Sequential Head (3→16→4)
- v4.10~v4.12: nn.Sequential Head (3→32→8)
- v4.12.lite: nn.Sequential Head (3→32→4)
- v4.13.lite: nn.Sequential Head (3→32→4)
- v4.13~v4.26.heavy: 自定义 Head 类（从 IFNet 文件导入）
"""

import importlib
from app.utils.logger import get_logger
import os
from typing import Optional

import torch
import torch.nn as nn

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 模型版本列表
# ---------------------------------------------------------------------------

SUPPORTED_MODELS = [
    "4.0",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "4.5",
    "4.6",
    "4.7",
    "4.8",
    "4.9",
    "4.10",
    "4.11",
    "4.12",
    "4.12.lite",
    "4.13",
    "4.13.lite",
    "4.14",
    "4.14.lite",
    "4.15",
    "4.15.lite",
    "4.16.lite",
    "4.17",
    "4.17.lite",
    "4.18",
    "4.19",
    "4.20",
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
]

# ---------------------------------------------------------------------------
# 各模型版本的配置
# ---------------------------------------------------------------------------

# Head 类型常量
HEAD_NONE = "none"  # 无 Head 编码器（v4.0~v4.6）
HEAD_SEQUENTIAL = "sequential"  # nn.Sequential Head（v4.7~v4.13.lite）
HEAD_CUSTOM = "custom"  # 自定义 Head 类，从 IFNet 文件导入（v4.13~v4.26.heavy）

MODEL_CONFIGS = {
    # v4.0~v4.6: 无 Head，4 block，ensemble 支持
    "4.0": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.1": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.2": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.3": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.4": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.5": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    "4.6": {
        "encode_channel": 0,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_NONE,
    },
    # v4.7~v4.9: nn.Sequential Head (3→16→4), encode_channel=4
    "4.7": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 16, "out_channels": 4},
    },
    "4.8": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 16, "out_channels": 4},
    },
    "4.9": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 16, "out_channels": 4},
    },
    # v4.10~v4.12: nn.Sequential Head (3→32→8), encode_channel=8
    "4.10": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 32, "out_channels": 8},
    },
    "4.11": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 32, "out_channels": 8},
    },
    "4.12": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 32, "out_channels": 8},
    },
    # v4.12.lite: nn.Sequential Head (3→32→4), encode_channel=4
    "4.12.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 32, "out_channels": 4},
    },
    # v4.13: 自定义 Head (32→8), encode_channel=8
    "4.13": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.13.lite: nn.Sequential Head (3→32→4), encode_channel=4
    "4.13.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_SEQUENTIAL,
        "head_config": {"in_channels": 3, "mid_channels": 32, "out_channels": 4},
    },
    # v4.14: 自定义 Head (32→8), encode_channel=8
    "4.14": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.14.lite: 自定义 Head (32→8), encode_channel=8, ResConv groups=2
    "4.14.lite": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.15: 自定义 Head (32→8), encode_channel=8
    "4.15": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.15.lite: 自定义 Head (16→4), encode_channel=4
    "4.15.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.16.lite: 自定义 Head (16→4), encode_channel=4
    "4.16.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.17: 自定义 Head (32→8), encode_channel=8
    "4.17": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.17.lite: 自定义 Head (16→4), encode_channel=4
    "4.17.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.18~v4.20: 自定义 Head (32→8), encode_channel=8
    "4.18": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    "4.19": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    "4.20": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": True,
        "head_type": HEAD_CUSTOM,
    },
    # v4.21~v4.24: 自定义 Head (32→8), feat 传播, 无 ensemble
    "4.21": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    "4.22": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    "4.22.lite": {
        "encode_channel": 4,
        "modulo": 32,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    "4.23": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    "4.24": {
        "encode_channel": 8,
        "modulo": 32,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    # v4.25: 自定义 Head (16→4), 5 block, modulo=64
    "4.25": {
        "encode_channel": 4,
        "modulo": 64,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    # v4.25.lite: 自定义 Head (16→4), 5 block, modulo=128
    "4.25.lite": {
        "encode_channel": 4,
        "modulo": 128,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    # v4.25.heavy: 自定义 Head (16→4), 5 block, 2x 宽, modulo=64
    "4.25.heavy": {
        "encode_channel": 4,
        "modulo": 64,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    # v4.26: 自定义 Head (16→4), 5 block, modulo=64
    "4.26": {
        "encode_channel": 4,
        "modulo": 64,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
    # v4.26.heavy: 自定义 Head (16→16), 5 block, modulo=64
    "4.26.heavy": {
        "encode_channel": 16,
        "modulo": 64,
        "ensemble": False,
        "head_type": HEAD_CUSTOM,
    },
}

# ---------------------------------------------------------------------------
# 版本号 → 模块名映射
# ---------------------------------------------------------------------------


def _version_to_module_name(version: str) -> str:
    """
    将版本号转换为 Python 模块名。

    例如：
        "4.25"       → "ifnet_v4_25"
        "4.12.lite"  → "ifnet_v4_12_lite"
        "4.26.heavy" → "ifnet_v4_26_heavy"
    """
    return "ifnet_v" + version.replace(".", "_")


# ---------------------------------------------------------------------------
# Head 构建
# ---------------------------------------------------------------------------


def _build_sequential_head(
    in_channels: int,
    mid_channels: int,
    out_channels: int,
) -> nn.Sequential:
    """
    构建 nn.Sequential 类型的 Head 编码器。

    参照 vs-rife __init__.py 中的 Head 构建逻辑：
    - in_channels=3, mid_channels=16, out_channels=4 → v4.7~v4.9
    - in_channels=3, mid_channels=32, out_channels=8 → v4.10~v4.12
    - in_channels=3, mid_channels=32, out_channels=4 → v4.12.lite, v4.13.lite
    """
    if mid_channels == 16 and out_channels == 4:
        # v4.7~v4.9: 简单两层，无 LeakyReLU
        return nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, 3, 2, 1),
            nn.ConvTranspose2d(mid_channels, out_channels, 4, 2, 1),
        )
    else:
        # v4.10+: 带中间层和 LeakyReLU
        return nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, 3, 2, 1),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(mid_channels, mid_channels, 3, 1, 1),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(mid_channels, mid_channels, 3, 1, 1),
            nn.LeakyReLU(0.2, True),
            nn.ConvTranspose2d(mid_channels, out_channels, 4, 2, 1),
        )


# ---------------------------------------------------------------------------
# 模型加载
# ---------------------------------------------------------------------------


def get_model_dir() -> str:
    """获取模型权重目录。"""
    # 相对于 backend/app/algorithms/rife/ → backend/models/
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    model_dir = os.path.join(backend_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def load_rife_model(
    model_version: str = "4.25",
    scale: float = 1.0,
    device: Optional[str] = None,
    fp16: bool = False,
    model_dir: Optional[str] = None,
) -> tuple[nn.Module, Optional[nn.Module], dict]:
    """
    加载 RIFE 模型（IFNet + Head 编码器）。

    参照 vs-rife 的 init_module 逻辑，根据版本配置：
    1. 动态导入对应版本的 IFNet（和 Head，如果存在）
    2. 加载 state_dict，移除 "module." 前缀
    3. 用 torch.device("meta") 创建模型骨架再 load_state_dict
    4. 分离 encode 权重到独立的 Head 编码器

    参数:
        model_version: 模型版本号（默认 "4.25"）
        scale: 处理分辨率缩放因子（1.0 原始分辨率，0.5 半分辨率适用于 4K）
        device: 推理设备（"cuda", "cuda:0", "cpu" 等，默认自动选择）
        fp16: 是否使用半精度推理
        model_dir: 模型权重目录（默认使用 backend/models/）

    返回:
        (flownet, encode, config) 元组:
        - flownet: IFNet 模型（eval 模式）
        - encode: Head 编码器（eval 模式），无 Head 时为 None
        - config: 模型配置字典（encode_channel, modulo, head_type 等）

    异常:
        FileNotFoundError: 权重文件不存在
    """
    if model_version not in MODEL_CONFIGS:
        raise ValueError(f"不支持的模型版本: {model_version}。可用版本: {SUPPORTED_MODELS}")

    config = MODEL_CONFIGS[model_version].copy()
    head_type = config["head_type"]

    # 确定设备
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_device = torch.device(device)

    # 确定数据类型
    dtype = torch.half if fp16 else torch.float

    # 确定模型目录
    if model_dir is None:
        model_dir = get_model_dir()

    # 检查权重文件
    filename = f"flownet_v{model_version}.pkl"
    weight_path = os.path.join(model_dir, filename)

    if not os.path.isfile(weight_path) or os.path.getsize(weight_path) == 0:
        raise FileNotFoundError(f"模型权重文件未找到: {weight_path}。请确保权重文件已预置于 {model_dir} 目录下")

    # 加载权重（旧格式 pkl 不支持 mmap，需使用 weights_only=False）
    logger.info(f"加载模型权重: {weight_path}")
    state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)
    # 移除 DistributedDataParallel 的 "module." 前缀
    state_dict = {k.replace("module.", ""): v for k, v in state_dict.items() if "module." in k}

    # 动态导入 IFNet（和 Head）
    module_name = _version_to_module_name(model_version)
    rife_package = f"app.algorithms.rife.{module_name}"
    logger.info(f"动态导入模块: {rife_package}")
    mod = importlib.import_module(rife_package)
    IFNet = mod.IFNet

    # 创建 IFNet
    ensemble = config.get("ensemble", False)
    with torch.device("meta"):
        flownet = IFNet(scale=scale, ensemble=ensemble)
    flownet.load_state_dict(state_dict, strict=False, assign=True)
    flownet.eval().to(torch_device, dtype)

    # 创建 Head 编码器
    encode = None
    if head_type == HEAD_CUSTOM:
        # 从 IFNet 模块导入自定义 Head 类
        Head = mod.Head
        encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}
        with torch.device("meta"):
            encode = Head()
        encode.load_state_dict(encode_state_dict, assign=True)
        encode.eval().to(torch_device, dtype)

    elif head_type == HEAD_SEQUENTIAL:
        # 构建 nn.Sequential Head
        head_config = config.get("head_config", {})
        with torch.device("meta"):
            encode = _build_sequential_head(
                in_channels=head_config.get("in_channels", 3),
                mid_channels=head_config.get("mid_channels", 16),
                out_channels=head_config.get("out_channels", 4),
            )
        encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}
        encode.load_state_dict(encode_state_dict, assign=True)
        encode.eval().to(torch_device, dtype)

    # HEAD_NONE 时 encode 保持 None

    logger.info(
        f"RIFE v{model_version} 模型加载完成 "
        f"(device={torch_device}, dtype={dtype}, scale={scale}, "
        f"head_type={head_type}, encode={'有' if encode is not None else '无'})"
    )

    return flownet, encode, config


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def create_backwarp_grid(height: int, width: int, device: torch.device) -> torch.Tensor:
    """
    创建后向变形的基础采样网格。

    参数:
        height: 帧高度
        width: 帧宽度
        device: 计算设备

    返回:
        采样网格，形状 (1, 2, H, W)
    """
    tenHorizontal = torch.linspace(-1.0, 1.0, width, dtype=torch.float, device=device)
    tenHorizontal = tenHorizontal.view(1, 1, 1, width).expand(-1, -1, height, -1)
    tenVertical = torch.linspace(-1.0, 1.0, height, dtype=torch.float, device=device)
    tenVertical = tenVertical.view(1, 1, height, 1).expand(-1, -1, -1, width)
    return torch.cat([tenHorizontal, tenVertical], 1)


def create_flow_div(height: int, width: int, device: torch.device) -> torch.Tensor:
    """
    创建光流归一化除数。

    参数:
        height: 帧高度
        width: 帧宽度
        device: 计算设备

    返回:
        归一化除数，形状 (2,)，值为 [(W-1)/2, (H-1)/2]
    """
    return torch.tensor(
        [(width - 1.0) / 2.0, (height - 1.0) / 2.0],
        dtype=torch.float,
        device=device,
    )


def pad_frame(img: torch.Tensor, modulo: int) -> tuple[torch.Tensor, tuple]:
    """
    将帧 padding 到 modulo 的倍数。

    参数:
        img: 输入帧张量，形状 (1, C, H, W)
        modulo: padding 模数

    返回:
        (padded_img, padding) 元组，padding 为 (left, right, top, bottom)
    """
    _, _, h, w = img.shape
    ph = ((h - 1) // modulo + 1) * modulo
    pw = ((w - 1) // modulo + 1) * modulo
    padding = (0, pw - w, 0, ph - h)
    if any(p > 0 for p in padding):
        img = torch.nn.functional.pad(img, padding)
    return img, padding


def unpad_frame(img: torch.Tensor, padding: tuple, orig_h: int, orig_w: int) -> torch.Tensor:
    """
    去除帧的 padding。

    参数:
        img: padding 后的帧张量，形状 (1, C, H', W')
        padding: pad_frame 返回的 padding 元组
        orig_h: 原始高度
        orig_w: 原始宽度

    返回:
        裁剪后的帧张量，形状 (1, C, orig_h, orig_w)
    """
    if any(p > 0 for p in padding):
        return img[:, :, :orig_h, :orig_w]
    return img
