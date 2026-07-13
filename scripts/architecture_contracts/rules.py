"""Declarative rules used by the architecture contract checker."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol


class ContractParseError(RuntimeError):
    """Raised when a contract source cannot be inspected."""


class ContractRule(Protocol):
    def check(self, root: Path) -> list[str]: ...


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_source(path: Path, root: Path) -> str:
    if not path.is_file():
        raise ContractParseError(f"missing file: {relative_path(path, root)}")
    return path.read_text(encoding="utf-8")


def _issue(message: str, path: str) -> str:
    return f"{message}: {path}"


def _check_pattern(
    *,
    root: Path,
    path: str,
    pattern: str,
    message: str,
    flags: int,
    required: bool,
) -> list[str]:
    matches = re.search(pattern, read_source(root / path, root), flags) is not None
    return [] if matches == required else [_issue(message, path)]


@dataclass(frozen=True, slots=True)
class _PatternRule:
    rule_id: str
    path: str
    pattern: str
    message: str
    flags: int = re.MULTILINE
    required: ClassVar[bool]

    def check(self, root: Path) -> list[str]:
        return _check_pattern(
            root=root,
            path=self.path,
            pattern=self.pattern,
            message=self.message,
            flags=self.flags,
            required=self.required,
        )


@dataclass(frozen=True, slots=True)
class ForbiddenPatternRule(_PatternRule):
    required = False


@dataclass(frozen=True, slots=True)
class RequiredPatternRule(_PatternRule):
    required = True


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
                source_path = relative_path(path, root)
                if not path.is_file() or source_path in excluded or path.suffix not in self.suffixes:
                    continue
                text = read_source(path, root)
                if any(re.search(pattern, text, self.flags) for pattern in self.patterns):
                    issues.append(_issue(self.message, source_path))
        return issues


def run_rules(root: Path, rules: list[ContractRule] | tuple[ContractRule, ...]) -> list[str]:
    issues: list[str] = []
    for rule in rules:
        issues.extend(rule.check(root))
    return issues
