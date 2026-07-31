"""Shared exact AST readers for neutral Python registries."""

from __future__ import annotations

import ast

from .rules import ContractParseError


def _top_level_assignment_value(tree: ast.Module, symbol: str) -> ast.expr:
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == symbol and statement.value is not None:
                return statement.value
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == symbol
        ):
            return statement.value
    raise ContractParseError(f"could not find {symbol!r}")


def _literal_dict(tree: ast.Module, symbol: str) -> ast.Dict:
    value = _top_level_assignment_value(tree, symbol)
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "MappingProxyType"
        and len(value.args) == 1
        and not value.keywords
    ):
        value = value.args[0]
    if not isinstance(value, ast.Dict):
        raise ContractParseError(f"{symbol!r} must be a literal dict or exact MappingProxyType wrapper")
    return value


def _literal_string_key(node: ast.expr | None, symbol: str) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise ContractParseError(f"{symbol!r} must use literal string keys")
    return node.value


def literal_string_keys(tree: ast.Module, symbol: str) -> tuple[str, ...]:
    keys = tuple(_literal_string_key(key, symbol) for key in _literal_dict(tree, symbol).keys)
    if len(keys) != len(set(keys)):
        raise ContractParseError(f"{symbol!r} contains duplicate keys")
    return keys


def literal_name_registry(tree: ast.Module, symbol: str) -> dict[str, str]:
    mapping = _literal_dict(tree, symbol)
    keys = literal_string_keys(tree, symbol)
    registry: dict[str, str] = {}
    for key, value in zip(keys, mapping.values, strict=True):
        if not isinstance(value, ast.Name):
            raise ContractParseError(f"{symbol!r} values must reference local factory functions")
        registry[key] = value.id
    return registry


def literal_string_pair_registry(tree: ast.Module, symbol: str) -> dict[str, tuple[str, str]]:
    mapping = _literal_dict(tree, symbol)
    keys = literal_string_keys(tree, symbol)
    registry: dict[str, tuple[str, str]] = {}
    for key, value in zip(keys, mapping.values, strict=True):
        if not (
            isinstance(value, (ast.Tuple, ast.List))
            and len(value.elts) == 2
            and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts)
        ):
            raise ContractParseError(f"{symbol!r} values must be literal (module, symbol) string pairs")
        registry[key] = (value.elts[0].value, value.elts[1].value)
    if len(registry.values()) != len(set(registry.values())):
        raise ContractParseError(f"{symbol!r} contains duplicate module/symbol targets")
    return registry
