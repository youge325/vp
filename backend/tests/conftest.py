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
    """Pre-load paddle 自带的 nvidia 运行时 DLL 到进程,避免系统其他位置的同名 DLL 冲突。

    paddle 在 ``import paddle`` 时通过 ``cudnn_cnn64_9.dll`` 链式加载 cudnn,
    cudnn 内部依赖 cudnn 同伴 DLL (cudnn_ops、cudnn_engines_*) **以及** CUDA
    toolkit 运行时 (cublas、cublasLt、cudart 等)。runner 上 paddle 通过两个
    namespace package 提供这些库:

    - ``nvidia.cudnn`` -> ``site-packages/nvidia/cudnn/bin``  (cudnn 9 全套)
    - ``nvidia.cu13`` -> ``site-packages/nvidia/cu13/bin/x86_64`` (CUDA 13 toolkit)

    仅靠 ``os.add_dll_directory`` + PATH 在某些 runner 上不够,因为:

    1. paddle 内部可能用 LoadLibraryW (默认搜索),不走 add_dll_directory 的
       user-dirs 列表;
    2. 系统目录 (System32 等) 在 LoadLibrary 搜索顺序里早于 PATH,如果系统装了
       NVIDIA 驱动级别的 cudnn,会被优先加载,导致版本不匹配 (WinError 127 /
       0xc0000139 STATUS_ENTRYPOINT_NOT_FOUND)。

    所以这里用 ``ctypes.WinDLL`` 按依赖顺序**显式预加载** paddle 自己的 cudnn
    和 CUDA toolkit DLL。一旦同名 DLL 已在进程中,Windows 不会再走 LoadLibrary
    搜索流程,paddle 后续 ``import`` 直接复用我们预加载的版本。
    """
    if sys.platform != "win32":
        return

    import ctypes
    import importlib.util

    cudnn_bin: str | None = None
    cu13_bin: str | None = None
    for spec_name, sub, target in (
        ("nvidia.cudnn", "bin", "cudnn"),
        ("nvidia.cu13", os.path.join("bin", "x86_64"), "cu13"),
    ):
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
        if not os.path.isdir(candidate):
            continue
        if target == "cudnn":
            cudnn_bin = candidate
        else:
            cu13_bin = candidate

    candidates = [d for d in (cudnn_bin, cu13_bin) if d]
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

    cuda_dlls = (
        "cudart64_13.dll",
        "cublas64_13.dll",
        "cublasLt64_13.dll",
        "cusparse64_12.dll",
        "cusolver64_12.dll",
        "cufft64_12.dll",
        "curand64_10.dll",
        "nvJitLink_130_0.dll",
        "nvrtc64_130_0.dll",
        "nvrtc-builtins64_132.dll",
    )
    cudnn_dlls = (
        "cudnn_ops64_9.dll",
        "cudnn_heuristic64_9.dll",
        "cudnn_engines_precompiled64_9.dll",
        "cudnn_engines_runtime_compiled64_9.dll",
        "cudnn_graph64_9.dll",
        "cudnn_adv64_9.dll",
        "cudnn_cnn64_9.dll",
        "cudnn64_9.dll",
    )

    def _preload(directory: str | None, names: tuple[str, ...]) -> None:
        if not directory:
            return
        for name in names:
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            try:
                ctypes.WinDLL(full)
            except OSError:
                pass

    _preload(cu13_bin, cuda_dlls)
    _preload(cudnn_bin, cudnn_dlls)


if _BACKEND == "paddle":
    _register_paddle_cudnn_dll_dir()
