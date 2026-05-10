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


def _register_paddle_cudnn_dll_dir() -> None:
    """注册 paddle 自带的 nvidia/cudnn/bin 到 DLL 搜索路径。

    paddle 在 ``import paddle`` 时尝试加载 ``cudnn_cnn64_9.dll`` 等 cudnn 库,
    但 cudnn 内部互相依赖 (cudnn_cnn 依赖 cudnn_ops、cudnn_engines_*)。如果
    nvidia/cudnn/bin 不在进程 DLL 搜索路径里,LoadLibrary 找到 cudnn_cnn64_9.dll
    后无法解析它的同伴依赖,会抛 ``OSError [WinError 127]``。

    通过 ``importlib`` 定位 ``nvidia.cudnn`` 包的物理目录,把 ``bin`` 子目录
    同时注册到 ``os.add_dll_directory`` (现代 LoadLibraryEx 搜索) 和 PATH 头部
    (legacy LoadLibrary 搜索),让 paddle 后续 import 能找到全部 cudnn DLL。
    """
    if sys.platform != "win32":
        return
    try:
        import importlib.util

        spec = importlib.util.find_spec("nvidia.cudnn")
    except (ImportError, ValueError):
        return
    if spec is None or not spec.submodule_search_locations:
        return
    cudnn_root = next(iter(spec.submodule_search_locations), None)
    if not cudnn_root:
        return
    cudnn_bin = os.path.join(cudnn_root, "bin")
    if not os.path.isdir(cudnn_bin):
        return
    try:
        os.add_dll_directory(cudnn_bin)
    except (OSError, AttributeError):
        pass
    current_path = os.environ.get("PATH", "")
    if cudnn_bin.lower() not in current_path.lower():
        os.environ["PATH"] = cudnn_bin + os.pathsep + current_path


if _BACKEND == "paddle":
    _register_paddle_cudnn_dll_dir()
