"""RIFE 模型加载器 — 权重加载、设备管理。

支持:
- 36 个 RIFE 模型版本(v4.0 ~ v4.26.heavy)
- 从本地路径加载权重(权重文件预置于 backend/models/ 目录)
- GPU/CPU 设备管理
- fp16 半精度推理
- 根据 Head 类型自动分离加载编码器

参考 vs-rife 的 init_module 逻辑:
- v4.0~v4.6: 无 Head 编码器,IFNet.forward 不接受 f0/f1
- v4.7~v4.9: nn.Sequential Head (3→16→4)
- v4.10~v4.12: nn.Sequential Head (3→32→8)
- v4.12.lite: nn.Sequential Head (3→32→4)
- v4.13.lite: nn.Sequential Head (3→32→4)
- v4.13~v4.26.heavy: 自定义 Head 类(从 IFNet 文件导入)

36 个模型配置统一保存在中立的 ``app.catalog.rife_models`` 表中。
本文件聚焦"如何加载权重 / 构 Head / 移动到设备"这条逻辑流。
"""

from __future__ import annotations

import importlib
import importlib.util
import os
from typing import TYPE_CHECKING, Optional

from app.catalog.rife_models import (
    HEAD_CUSTOM as _HEAD_CUSTOM,
    HEAD_NONE as _HEAD_NONE,
    HEAD_SEQUENTIAL as _HEAD_SEQUENTIAL,
    SUPPORTED_MODELS as _SUPPORTED_MODELS,
    RifeModelSpec,
    get_spec as _get_spec,
)
from app.utils.logger import get_logger

if TYPE_CHECKING:
    import torch
    import torch.nn as nn

logger = get_logger(__name__)


__all__ = [
    "create_backwarp_grid",
    "create_flow_div",
    "get_model_dir",
    "load_rife_model",
    "pad_frame",
    "unpad_frame",
]


# ---------------------------------------------------------------------------
# 版本号 → 模块名映射
# ---------------------------------------------------------------------------


def _version_to_module_name(version: str) -> str:
    """
    将版本号转换为 Python 模块名。

    例如:
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
) -> "nn.Sequential":
    """构建 nn.Sequential 类型的 Head 编码器。

    参照 vs-rife __init__.py 中的 Head 构建逻辑:
    - in_channels=3, mid_channels=16, out_channels=4 → v4.7~v4.9
    - in_channels=3, mid_channels=32, out_channels=8 → v4.10~v4.12
    - in_channels=3, mid_channels=32, out_channels=4 → v4.12.lite, v4.13.lite
    """
    import torch.nn as nn

    if mid_channels == 16 and out_channels == 4:
        # v4.7~v4.9: 简单两层,无 LeakyReLU
        return nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, 3, 2, 1),
            nn.ConvTranspose2d(mid_channels, out_channels, 4, 2, 1),
        )
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
    env_model_dir = os.environ.get("VP_RIFE_MODEL_DIR")
    if env_model_dir:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(env_model_dir)))

    from app.config import settings

    model_dir = settings.RIFE_MODEL_DIR
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def _load_weights(weight_path: str) -> dict:
    """Load and de-DDP a state_dict from a .pkl checkpoint.

    The old RIFE checkpoints were saved from a DistributedDataParallel
    wrapper; their keys all carry a ``module.`` prefix. We strip it here
    so downstream ``load_state_dict`` calls can match the bare module
    hierarchy of the meta-device-constructed IFNet.
    """
    import torch

    logger.info(f"加载模型权重: {weight_path}")
    state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)
    return {k.replace("module.", ""): v for k, v in state_dict.items() if "module." in k}


def _build_head_for_spec(
    spec: RifeModelSpec,
    mod,
    state_dict: dict,
    torch_device: "torch.device",
    dtype: "torch.dtype",
) -> "nn.Module | None":
    """Create the Head encoder, load its weights, and move to device.

    Returns ``None`` for ``HEAD_NONE`` versions. Centralises the three
    Head-construction branches that used to live inline in
    ``load_rife_model``.
    """
    import torch

    head_type = spec.head_type
    if head_type == _HEAD_NONE:
        return None

    encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}

    if head_type == _HEAD_CUSTOM:
        head_cls = mod.Head
        with torch.device("meta"):
            encode = head_cls()
    elif head_type == _HEAD_SEQUENTIAL:
        head_config = spec.head_config or {}
        with torch.device("meta"):
            encode = _build_sequential_head(
                in_channels=head_config.get("in_channels", 3),
                mid_channels=head_config.get("mid_channels", 16),
                out_channels=head_config.get("out_channels", 4),
            )
    else:  # pragma: no cover - guarded by spec table
        raise ValueError(f"Unknown head_type {head_type!r}")

    encode.load_state_dict(encode_state_dict, assign=True)
    encode.eval().to(torch_device, dtype)
    return encode


def _compile_with_tensorrt_if_available(
    module: "nn.Module",
    *,
    label: str,
    fp16: bool,
) -> "nn.Module":
    """Wrap ``module`` with ``torch.compile(backend='tensorrt')``.

    A requested TensorRT engine must actually use TensorRT. Missing
    dependencies or compile errors are surfaced instead of falling back to
    CUDA, so diagnostics cannot count fallback as a TensorRT pass.
    """
    import torch

    from app.utils.dll_paths import register_native_dll_paths

    register_native_dll_paths()
    if importlib.util.find_spec("torch_tensorrt") is None:
        raise RuntimeError(
            "RIFE PyTorch TensorRT engine requires torch_tensorrt, but the package is not importable. "
            "Install a torch-tensorrt wheel compatible with the current PyTorch runtime."
        )
    import torch_tensorrt  # noqa: F401

    logger.info(f"正在使用 torch_tensorrt 编译 {label} 模型...")
    try:
        return torch.compile(
            module,
            backend="tensorrt",
            options={
                "truncate_long_and_double": True,
                "precision": "fp16" if fp16 else "fp32",
                "require_full_compilation": True,
                "pass_through_build_failures": True,
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to compile {label} with torch_tensorrt.") from exc


def load_rife_model(
    model_version: str = "4.25",
    scale: float = 1.0,
    device: Optional[str] = None,
    fp16: bool = False,
    model_dir: Optional[str] = None,
    engine: str = "cuda",
) -> tuple["nn.Module", "Optional[nn.Module]", RifeModelSpec]:
    """加载 RIFE 模型(IFNet + Head 编码器)。

    参照 vs-rife 的 init_module 逻辑,根据中立 model catalog 查表得到的
    ``RifeModelSpec``:

    1. 动态导入对应版本的 IFNet(和 Head,如果存在)
    2. 加载 state_dict,移除 "module." 前缀
    3. 用 torch.device("meta") 创建模型骨架再 load_state_dict
    4. 按 spec.head_type 分发到 ``_build_head_for_spec``

    参数:
        model_version: 模型版本号(默认 "4.25")
        scale: 处理分辨率缩放因子(1.0 原始分辨率,0.5 半分辨率适用于 4K)
        device: 推理设备("cuda", "cuda:0", "cpu" 等,默认自动选择)
        fp16: 是否使用半精度推理
        model_dir: 模型权重目录(默认使用 backend/models/)
        engine: 推理引擎("cuda" 或 "tensorrt",默认 "cuda")

    返回:
        ``(flownet, encode, spec)`` 元组:
        - flownet: IFNet 模型(eval 模式)
        - encode: Head 编码器(eval 模式),无 Head 时为 None
        - spec: 中立 catalog 中的不可变模型描述

    异常:
        FileNotFoundError: 权重文件不存在
        ValueError: 不支持的模型版本
    """
    import torch

    try:
        spec = _get_spec(model_version)
    except KeyError:
        raise ValueError(f"不支持的模型版本: {model_version}。可用版本: {_SUPPORTED_MODELS}")

    # 确定设备 / dtype / 模型目录
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_device = torch.device(device)
    dtype = torch.half if fp16 else torch.float

    if not model_dir:
        model_dir = get_model_dir()

    weight_path = os.path.join(model_dir, f"flownet_v{model_version}.pkl")
    if not os.path.isfile(weight_path) or os.path.getsize(weight_path) == 0:
        raise FileNotFoundError(f"模型权重文件未找到: {weight_path}。请确保权重文件已预置于 {model_dir} 目录下")

    state_dict = _load_weights(weight_path)

    # 动态导入 IFNet(和 Head)
    module_name = _version_to_module_name(model_version)
    rife_package = f"app.algorithms.pytorch.rife.{module_name}"
    logger.info(f"动态导入模块: {rife_package}")
    mod = importlib.import_module(rife_package)
    ifnet_cls = mod.IFNet

    # 构建 IFNet
    with torch.device("meta"):
        flownet = ifnet_cls(scale=scale, ensemble=spec.ensemble)
    flownet.load_state_dict(state_dict, strict=False, assign=True)
    flownet.eval().to(torch_device, dtype)

    # 构建 Head (None for HEAD_NONE versions)
    encode = _build_head_for_spec(spec, mod, state_dict, torch_device, dtype)

    # TensorRT 编译(可选)
    if engine == "tensorrt" and torch_device.type == "cuda":
        flownet = _compile_with_tensorrt_if_available(flownet, label=f"RIFE v{model_version}", fp16=fp16)
        if encode is not None:
            encode = _compile_with_tensorrt_if_available(encode, label=f"RIFE v{model_version} Head", fp16=fp16)

    logger.info(
        f"RIFE v{model_version} 模型加载完成 "
        f"(device={torch_device}, dtype={dtype}, scale={scale}, engine={engine}, "
        f"head_type={spec.head_type}, encode={'有' if encode is not None else '无'})"
    )

    return flownet, encode, spec


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def create_backwarp_grid(height: int, width: int, device: "torch.device") -> "torch.Tensor":
    """创建后向变形的基础采样网格。

    参数:
        height: 帧高度
        width: 帧宽度
        device: 计算设备

    返回:
        采样网格,形状 (1, 2, H, W)
    """
    import torch

    horizontal = torch.linspace(-1.0, 1.0, width, dtype=torch.float, device=device)
    horizontal = horizontal.view(1, 1, 1, width).expand(-1, -1, height, -1)
    vertical = torch.linspace(-1.0, 1.0, height, dtype=torch.float, device=device)
    vertical = vertical.view(1, 1, height, 1).expand(-1, -1, -1, width)
    return torch.cat([horizontal, vertical], 1)


def create_flow_div(height: int, width: int, device: "torch.device") -> "torch.Tensor":
    """创建光流归一化除数。

    返回:
        归一化除数,形状 (2,),值为 [(W-1)/2, (H-1)/2]
    """
    import torch

    return torch.tensor(
        [(width - 1.0) / 2.0, (height - 1.0) / 2.0],
        dtype=torch.float,
        device=device,
    )


def pad_frame(img: "torch.Tensor", modulo: int) -> "tuple[torch.Tensor, tuple]":
    """将帧 padding 到 modulo 的倍数。

    返回:
        ``(padded_img, padding)`` 元组,padding 为 (left, right, top, bottom)
    """
    import torch

    _, _, h, w = img.shape
    ph = ((h - 1) // modulo + 1) * modulo
    pw = ((w - 1) // modulo + 1) * modulo
    padding = (0, pw - w, 0, ph - h)
    if any(p > 0 for p in padding):
        img = torch.nn.functional.pad(img, padding)
    return img, padding


def unpad_frame(img: "torch.Tensor", padding: tuple, orig_h: int, orig_w: int) -> "torch.Tensor":
    """去除帧的 padding。

    返回:
        裁剪后的帧张量,形状 (1, C, orig_h, orig_w)
    """
    if any(p > 0 for p in padding):
        return img[:, :, :orig_h, :orig_w]
    return img
