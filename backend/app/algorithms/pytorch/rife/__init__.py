"""RIFE 模型子包 — 提供 RIFESolver 统一推理接口。

RIFESolver 封装了模型加载、帧对推理、padding/裁剪等细节,
外部只需调用 interpolate(img0, img1, timestep) 即可获取中间帧。

支持全部 36 个 RIFE 模型版本（v4.0 ~ v4.26.heavy），自动根据
Head 类型选择推理路径：
- 无 Head（v4.0~v4.6）: IFNet(img0, img1, t, flow_div, grid)
- 有 Head（v4.7+）: IFNet(img0, img1, t, flow_div, grid, f0, f1)

注意: ``RIFESolver`` 实际定义在 ``app.algorithms.pytorch.rife.solver`` 子模块,
该子模块顶层 ``import torch``。这里通过模块级 ``__getattr__`` 提供
延迟导入,确保 ``import app.algorithms.pytorch.rife`` 不会无意间把 PyTorch
拉进当前进程 (paddle / pytorch 不能同进程共存)。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.algorithms.pytorch.rife.solver import RIFESolver  # noqa: F401


def __getattr__(name: str):
    if name == "RIFESolver":
        from app.algorithms.pytorch.rife.solver import RIFESolver as _RIFESolver

        return _RIFESolver
    raise AttributeError(f"module 'app.algorithms.pytorch.rife' has no attribute {name!r}")
