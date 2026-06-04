#!/usr/bin/env python3
"""Architecture boundary checks for VP Workbench.

The checks are intentionally small and dependency-free so they can run from
pre-commit, CI, or a local shell before broader frontend/backend test suites.
They protect contracts that are easy to break through otherwise harmless
renames: the Tauri command surface, docs command names, generated-type import
boundaries, and direct IPC access from UI/store layers.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS_MANIFEST = ROOT / "frontend" / "src-tauri" / "src" / "commands_manifest.rs"
DEFAULT_PERMISSIONS = ROOT / "frontend" / "src-tauri" / "permissions" / "default.toml"
IPC_ENDPOINT_DIR = ROOT / "frontend" / "src" / "lib" / "ipc" / "endpoints"
FRONTEND_SRC = ROOT / "frontend" / "src"
DOC_ROOT = ROOT / "docs"
README = ROOT / "README.md"


def _read(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _iter_source_files(*roots: Path) -> list[Path]:
    suffixes = {".ts", ".tsx", ".vue"}
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                files.append(path)
    return files


def _is_test_file(path: Path) -> bool:
    parts = set(path.parts)
    return path.name.endswith(".spec.ts") or "__tests__" in parts or "e2e" in parts


def _allow_token(command: str) -> str:
    return f"allow-{command.replace('_', '-')}"


def _collect_manifest_commands() -> set[str]:
    text = _read(COMMANDS_MANIFEST)
    match = re.search(r"APP_COMMAND_NAMES:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];", text, re.DOTALL)
    if not match:
        raise RuntimeError("could not parse APP_COMMAND_NAMES in commands_manifest.rs")
    return set(re.findall(r'"([a-z_]+)"', match.group("body")))


def _collect_permission_commands() -> set[str]:
    text = _read(DEFAULT_PERMISSIONS)
    tokens = set(re.findall(r'"(allow-[a-z-]+)"', text))
    return {token.removeprefix("allow-").replace("-", "_") for token in tokens}


def _collect_frontend_invoke_commands() -> set[str]:
    commands: set[str] = set()
    pattern = re.compile(r"safeInvoke(?:<[^>]+>)?\(\s*['\"]([a-z_]+)['\"]")
    for path in _iter_source_files(IPC_ENDPOINT_DIR):
        commands.update(pattern.findall(_read(path)))
    return commands


def _check_command_surface(issues: list[str]) -> None:
    manifest = _collect_manifest_commands()
    permissions = _collect_permission_commands()
    invokes = _collect_frontend_invoke_commands()

    expected_permissions = {_allow_token(command) for command in manifest}
    raw_permission_tokens = set(re.findall(r'"(allow-[a-z-]+)"', _read(DEFAULT_PERMISSIONS)))
    if raw_permission_tokens != expected_permissions:
        issues.append(
            "Tauri permission command tokens drift: "
            f"missing={sorted(expected_permissions - raw_permission_tokens)}, "
            f"extra={sorted(raw_permission_tokens - expected_permissions)}"
        )

    if permissions != manifest:
        issues.append(
            "commands_manifest.rs and permissions/default.toml drift: "
            f"only-in-manifest={sorted(manifest - permissions)}, "
            f"only-in-permissions={sorted(permissions - manifest)}"
        )

    if invokes != manifest:
        issues.append(
            "frontend IPC endpoint safeInvoke commands drift from command manifest: "
            f"only-in-manifest={sorted(manifest - invokes)}, only-in-frontend={sorted(invokes - manifest)}"
        )


def _check_docs_do_not_reference_legacy_commands(issues: list[str]) -> None:
    legacy = ("pause_task", "resume_task")
    doc_files = [README, *sorted(DOC_ROOT.rglob("*.md"))]
    for path in doc_files:
        text = _read(path)
        for token in legacy:
            if token in text:
                issues.append(f"legacy command `{token}` remains in docs file {_rel(path)}")


def _check_generated_type_import_boundary(issues: list[str]) -> None:
    allowed_dir = FRONTEND_SRC / "types" / "protocol"
    generated_dir = FRONTEND_SRC / "types" / "generated"
    for path in _iter_source_files(FRONTEND_SRC):
        if _is_test_file(path):
            continue
        if allowed_dir in path.parents or generated_dir in path.parents:
            continue
        if "@/types/generated/" in _read(path):
            issues.append(f"generated type deep import outside protocol layer: {_rel(path)}")


def _check_ui_and_store_ipc_boundary(issues: list[str]) -> None:
    restricted_roots = [
        FRONTEND_SRC / "views",
        FRONTEND_SRC / "components",
        FRONTEND_SRC / "stores",
    ]
    markers = ("@/lib/ipc", "@tauri-apps/api", "safeInvoke(")
    for path in _iter_source_files(*restricted_roots):
        if _is_test_file(path):
            continue
        text = _read(path)
        if any(marker in text for marker in markers):
            issues.append(f"direct IPC access in UI/store layer: {_rel(path)}")


def main() -> int:
    issues: list[str] = []
    try:
        _check_command_surface(issues)
        _check_docs_do_not_reference_legacy_commands(issues)
        _check_generated_type_import_boundary(issues)
        _check_ui_and_store_ipc_boundary(issues)
    except RuntimeError as exc:
        sys.stderr.write(f"[check-architecture-contracts] PARSE ERROR: {exc}\n")
        return 2

    if issues:
        sys.stderr.write("[check-architecture-contracts] DRIFT DETECTED:\n")
        for issue in issues:
            sys.stderr.write(f"  - {issue}\n")
        return 1

    sys.stdout.write("[check-architecture-contracts] OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
