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
    """注册 paddle 自带的 nvidia 运行时 DLL 目录到 DLL 搜索路径。

    paddle 在 ``import paddle`` 时通过 ``cudnn_cnn64_9.dll`` 链式加载 cudnn,
    cudnn 内部依赖 cudnn 同伴 DLL (cudnn_ops、cudnn_engines_*) **以及** CUDA
    toolkit 运行时 (cublas、cublasLt、cudart 等)。runner 上 paddle 通过两个
    namespace package 提供这些库:

    - ``nvidia.cudnn`` -> ``site-packages/nvidia/cudnn/bin``  (cudnn 9 全套)
    - ``nvidia.cu13`` -> ``site-packages/nvidia/cu13/bin/x86_64`` (CUDA 13 toolkit)

    如果这两个目录都没注册到进程 DLL 搜索路径里, ``LoadLibrary`` 解析
    ``cudnn_cnn64_9.dll`` 的传递依赖时会失败,抛 ``OSError [WinError 127]``。
    paddle 自身的 ``__init__`` 不可靠地处理这件事,因此这里在测试启动前手动
    把两个目录注册到 ``os.add_dll_directory`` (现代 LoadLibraryEx 搜索) 和
    PATH 头部 (legacy LoadLibrary 搜索)。
    """
    if sys.platform != "win32":
        return

    import importlib.util

    candidates: list[str] = []
    for spec_name, sub in (("nvidia.cudnn", "bin"), ("nvidia.cu13", os.path.join("bin", "x86_64"))):
        try:
            spec = importlib.util.find_spec(spec_name)
        except (ImportError, ValueError):
            continue
        if spec is None or not spec.submodule_search_locations:
            continue
        root = next(iter(spec.submodule_search_locations), None)
        if not root:
            continue
        candidate = os.path.join(root, sub)
        if os.path.isdir(candidate):
            candidates.append(candidate)

    if not candidates:
        return

    for candidate in candidates:
        try:
            os.add_dll_directory(candidate)
        except (OSError, AttributeError):
            pass

    current_path = os.environ.get("PATH", "")
    lower_path = current_path.lower()
    new_prefix = [c for c in candidates if c.lower() not in lower_path]
    if new_prefix:
        os.environ["PATH"] = os.pathsep.join(new_prefix) + os.pathsep + current_path


if _BACKEND == "paddle":
    _register_paddle_cudnn_dll_dir()
