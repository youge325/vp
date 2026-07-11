"""Declarative rules used by the architecture contract checker."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ContractParseError(RuntimeError):
    """Raised when a contract source cannot be inspected."""


class ContractRule(Protocol):
    def check(self, root: Path) -> list[str]: ...


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read(root: Path, relative_path: str) -> str:
    path = root / relative_path
    if not path.is_file():
        raise ContractParseError(f"missing file: {relative_path}")
    return path.read_text(encoding="utf-8")


def _issue(message: str, path: str) -> str:
    return f"{message}: {path}"


@dataclass(frozen=True, slots=True)
class ForbiddenPatternRule:
    rule_id: str
    path: str
    pattern: str
    message: str
    flags: int = re.MULTILINE

    def check(self, root: Path) -> list[str]:
        text = _read(root, self.path)
        if re.search(self.pattern, text, self.flags):
            return [_issue(self.message, self.path)]
        return []


@dataclass(frozen=True, slots=True)
class RequiredPatternRule:
    rule_id: str
    path: str
    pattern: str
    message: str
    flags: int = re.MULTILINE

    def check(self, root: Path) -> list[str]:
        text = _read(root, self.path)
        if not re.search(self.pattern, text, self.flags):
            return [_issue(self.message, self.path)]
        return []


@dataclass(frozen=True, slots=True)
class AbsentPathRule:
    rule_id: str
    path: str
    message: str

    def check(self, root: Path) -> list[str]:
        if (root / self.path).exists():
            return [_issue(self.message, self.path)]
        return []


@dataclass(frozen=True, slots=True)
class ForbiddenReferenceRule:
    rule_id: str
    roots: tuple[str, ...]
    patterns: tuple[str, ...]
    message: str
    suffixes: tuple[str, ...]
    excludes: tuple[str, ...] = ()
    flags: int = re.MULTILINE

    def check(self, root: Path) -> list[str]:
        excluded = set(self.excludes)
        issues: list[str] = []
        for relative_root in self.roots:
            search_root = root / relative_root
            if not search_root.exists():
                raise ContractParseError(f"missing reference root: {relative_root}")
            paths = [search_root] if search_root.is_file() else sorted(search_root.rglob("*"))
            for path in paths:
                relative_path = _relative(path, root)
                if not path.is_file() or relative_path in excluded or path.suffix not in self.suffixes:
                    continue
                text = path.read_text(encoding="utf-8")
                if any(re.search(pattern, text, self.flags) for pattern in self.patterns):
                    issues.append(_issue(self.message, relative_path))
        return issues


def run_rules(root: Path, rules: list[ContractRule] | tuple[ContractRule, ...]) -> list[str]:
    issues: list[str] = []
    for rule in rules:
        issues.extend(rule.check(root))
    return issues
