"""Generate and render TypeScript contract bindings."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .context import ROOT, _pascal_case
from .process_tools import _run


def _generate_typescript(schema: Path, output: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required to generate TypeScript contracts")
    _run(
        [
            npm,
            "exec",
            "--",
            "json2ts",
            "-i",
            str(schema),
            "-o",
            str(output),
            "--bannerComment",
            f"/* Generated from contracts/{schema.name}. Do not edit. */",
        ],
        cwd=ROOT / "frontend",
    )


def _render_ipc_contract(manifest: dict[str, Any]) -> str:
    imported_types = sorted(
        {
            type_name.removesuffix("[]").removesuffix("|null")
            for command in manifest["commands"]
            for type_name in [*command["args"].values(), command["result"]]
            if type_name not in {"boolean", "string", "string[]", "string|null", "void"}
        }
    )
    lines = [
        "/* Generated from contracts/ipc-manifest.json. Do not edit. */",
        "",
    ]
    if imported_types:
        lines.extend(
            [
                "import type {",
                *(f"  {name}," for name in imported_types),
                "} from '@/types/protocol'",
            ]
        )
    lines.extend(["", "interface IpcCommandArgs {"])
    for command in manifest["commands"]:
        args = command["args"]
        shape = "undefined" if not args else "{ " + "; ".join(f"{name}: {kind}" for name, kind in args.items()) + " }"
        lines.append(f"  {command['name']}: {shape}")
    lines.extend(["}", "", "export type IpcCommand = keyof IpcCommandArgs", "", "interface IpcCommandResult {"])
    lines.extend(f"  {command['name']}: {command['result']}" for command in manifest["commands"])
    lines.extend(
        [
            "}",
            "",
            "export type IpcInvokeArgs<C extends IpcCommand> = IpcCommandArgs[C]",
            "export type IpcInvokeResult<C extends IpcCommand> = IpcCommandResult[C]",
            "",
        ]
    )
    return "\n".join(lines)


def _render_typescript_events(manifest: dict[str, Any]) -> str:
    events = manifest["events"]
    constants = manifest["protocolConstants"]
    payloads = sorted({event["payload"] for event in events})
    lines = [
        "/* Generated from contracts/ipc-manifest.json. Do not edit. */",
        "",
        "import type {",
        *(f"  {payload}," for payload in payloads),
        "} from '@/types/generated/contracts'",
        "",
        "export const TASK_EVENT_NAMES = {",
        *(f"  {_pascal_case(event['name'])}: '{event['name']}'," for event in events),
        "} as const",
        "",
        "export type TaskEventName = (typeof TASK_EVENT_NAMES)[keyof typeof TASK_EVENT_NAMES]",
        "",
        "export interface TaskEventPayloadMap {",
        *(f"  '{event['name']}': {event['payload']}" for event in events),
        "}",
        "",
        f"export const TERMINAL_PROGRESS_PREFIX = {constants['terminalProgressPrefix']!r}",
        "",
    ]
    return "\n".join(lines)
