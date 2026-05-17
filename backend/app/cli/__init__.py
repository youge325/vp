"""VP Workbench CLI entry-point package.

Re-exports the minimal public surface for ``python -m app``.

Phase D.6.1 — 旧版本的 re-export 墙(70 行)被拆除。所有下划线前缀的
内部 helper(``_default_*_config``、``_resolve_*``、``_load_json_arg``
等)需要从它们各自的子模块直接 import:

    - ``app.cli.defaults``:配置默认值与 processing-step 解析
    - ``app.cli.parser``:argparse 构造
    - ``app.cli.commands._process_validation``:JSON / 输入校验
    - ``app.cli.commands._process_planning``:模型路径与 ONNX 校验
    - ``app.cli.commands._process_execution``:format-conversion / resume

本模块只保留 4 个 ``cmd_*`` handler、``main`` 入口、``build_parser`` 与
两个枚举映射,对外承诺最小公共面。
"""

from __future__ import annotations

from app.cli.commands.check import cmd_check
from app.cli.commands.info import cmd_info
from app.cli.commands.inspect_output import cmd_inspect_output
from app.cli.commands.process import cmd_process
from app.cli.defaults import PROCESS_LABEL_MAP, PROCESS_ORDER_MAP
from app.cli.main import main
from app.cli.parser import build_parser

__all__ = [
    "main",
    "build_parser",
    "cmd_check",
    "cmd_info",
    "cmd_process",
    "cmd_inspect_output",
    "PROCESS_LABEL_MAP",
    "PROCESS_ORDER_MAP",
]
