"""Pytest 配置和共享夹具。

paddle / pytorch 不共用 cudnn DLL,在同一进程加载会触发 cudnn 冲突。
通过 ``VP_TEST_BACKEND`` 环境变量在 *collect* 阶段就排除冲突文件,
避免 collect 时模块级 ``import torch`` / ``import paddle`` 把不兼容的运行时拉进同一进程。

- 未设置 (默认) : 排除所有 paddle / pytorch 后端测试,只跑共享 + onnx 层
- ``pytorch``    : 仅排除 paddle 测试
- ``paddle``     : 仅排除 pytorch 测试
"""

import os
import sys

# 确保 backend app 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


_BACKEND = os.environ.get("VP_TEST_BACKEND", "").strip().lower()

_PYTORCH_ONLY_FILES = [
    os.path.join("test_algorithms", "test_tensor_backend_pytorch.py"),
    os.path.join("test_algorithms", "test_rife_all_models.py"),
    os.path.join("test_algorithms", "test_rife_onnx.py"),
    os.path.join("test_algorithms", "test_interpolation.py"),
    "test_weight_loading.py",
]
_PADDLE_ONLY_FILES = [
    os.path.join("test_algorithms", "test_tensor_backend_paddle.py"),
]

if _BACKEND == "pytorch":
    collect_ignore = list(_PADDLE_ONLY_FILES)
elif _BACKEND == "paddle":
    collect_ignore = list(_PYTORCH_ONLY_FILES)
else:
    collect_ignore = list(_PYTORCH_ONLY_FILES) + list(_PADDLE_ONLY_FILES)
