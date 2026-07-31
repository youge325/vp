"""Pytest 配置和共享夹具。

paddle / pytorch 不共用 cudnn DLL,在同一进程加载会触发 cudnn 冲突。
通过 ``VP_TEST_BACKEND`` 环境变量在 *collect* 阶段就排除冲突文件,
避免 collect 时模块级 ``import torch`` / ``import paddle`` 把不兼容的运行时拉进同一进程。

- 未设置 (默认) : 排除所有 paddle / pytorch 后端测试,只跑共享 + onnx 层
- ``pytorch``    : 仅排除 paddle 测试
- ``paddle``     : 仅排除 pytorch 测试
"""

import ast
import os
import sys
from pathlib import Path

# 确保 backend app 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


_BACKEND = os.environ.get("VP_TEST_BACKEND", "").strip().lower()
_TEST_ROOT = Path(__file__).resolve().parent


def _is_backend_marker(node: ast.expr, marker: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == marker
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _module_backend_markers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    markers: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            continue
        values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else (node.value,)
        for marker in ("paddle", "pytorch"):
            if any(_is_backend_marker(value, marker) for value in values):
                markers.add(marker)
    return markers


def _backend_marked_files(test_root: Path, marker: str) -> list[str]:
    return [
        str(path.relative_to(test_root))
        for path in sorted(test_root.rglob("test_*.py"))
        if marker in _module_backend_markers(path)
    ]


_PYTORCH_ONLY_FILES = _backend_marked_files(_TEST_ROOT, "pytorch")
_PADDLE_ONLY_FILES = _backend_marked_files(_TEST_ROOT, "paddle")

if _BACKEND == "pytorch":
    collect_ignore = _PADDLE_ONLY_FILES
elif _BACKEND == "paddle":
    collect_ignore = _PYTORCH_ONLY_FILES
else:
    collect_ignore = [*_PYTORCH_ONLY_FILES, *_PADDLE_ONLY_FILES]
