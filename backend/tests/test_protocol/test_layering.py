"""Protocol 层无反向 import 的 AST 校验测试。

``app.protocol`` 是 NDJSON wire 协议的 leaf 层 —— 它应只被上层
(``app.processing``、``app.cli``、``app.errors`` 等)消费,自己不可
反向 import 任何 ``app.processing.*`` / ``app.cli.*`` 模块。

历史上 ``app.protocol.reporter`` 曾经直接 ``from
app.processing.streaming.metrics import PipelineMetrics``,造成了
``protocol → processing`` 的反向 import。现在 reporter 用私有结构化
Protocol 表达最小 read contract;本测试把分层约束变成机器断言。
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

PROTOCOL_PKG = Path(__file__).resolve().parents[2] / "app" / "protocol"

# 严格禁止 protocol 层 import 这些上层包。
# (允许 ``from app.errors.codes import ...`` 之类的低层 sibling,
#  但 protocol 层目前并不需要 errors,所以也一并禁止。)
FORBIDDEN_PREFIXES = (
    "app.processing",
    "app.cli",
    "app.algorithms",
    "app.planning",
)


def _iter_python_modules() -> list[Path]:
    return sorted(p for p in PROTOCOL_PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _collect_imports(tree: ast.AST) -> list[str]:
    """Return every module name referenced by ``import`` / ``from ... import``."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_protocol_package_present_and_non_empty() -> None:
    modules = _iter_python_modules()
    # Sanity:协议 emitter 与 reporter 必须存在。
    names = {m.name for m in modules}
    assert {"__init__.py", "emitter.py", "encoding.py", "reporter.py"} <= names, (
        f"protocol 包结构异常,实际文件: {names}"
    )


def test_package_initializers_do_not_load_concrete_error_or_protocol_modules() -> None:
    backend_root = PROTOCOL_PKG.parents[1]
    script = (
        "import sys\n"
        "import app.errors\n"
        "import app.protocol\n"
        "forbidden = {'app.errors.process', 'app.errors.codes', 'app.protocol.emitter', "
        "'app.generated.contracts', 'pydantic'}\n"
        "raise SystemExit(1 if forbidden.intersection(sys.modules) else 0)\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_protocol_does_not_reverse_import_upper_layers() -> None:
    """``app.protocol.*`` 严禁 import ``app.processing`` / ``app.cli`` 等上层。"""
    offenders: list[tuple[str, str]] = []
    for path in _iter_python_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _collect_imports(tree):
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES):
                offenders.append((path.relative_to(PROTOCOL_PKG.parent.parent).as_posix(), module))

    assert not offenders, (
        "protocol 层出现了反向 import,违反 layering 约束:\n"
        + "\n".join(f"  - {file}: {mod}" for file, mod in offenders)
        + "\n如需抽象上层对象,在叶层消费者内定义最小 Protocol 接口。"
    )
