"""Python catalog, boundary, import, and production-consumer checks."""

from __future__ import annotations

import ast
import json
import re
from functools import cache
from pathlib import Path

from .graph_ast import _find_dependency_cycles, _parse_python
from .python_ast import literal_name_registry, literal_string_keys, literal_string_pair_registry
from .rules import ContractParseError, read_source, relative_path


def _collect_python_dict_keys(text: str, symbol: str) -> set[str]:
    return set(literal_string_keys(ast.parse(text), symbol))


def _collect_python_name_registry(text: str, symbol: str) -> dict[str, str]:
    """Read an exact literal ``str -> local name`` registry."""
    return literal_name_registry(ast.parse(text), symbol)


def _static_descriptor_value(node: ast.expr) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
    ):
        return frozenset(ast.literal_eval(node.args[0]))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_GeometryPolicy":
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            raise ContractParseError("_GeometryPolicy requires one literal geometry kind")
        if any(keyword.arg != "fixed_scale_factor" for keyword in node.keywords):
            raise ContractParseError("_GeometryPolicy contains an unsupported field")
        fixed_scale = next(
            (
                _static_descriptor_value(keyword.value)
                for keyword in node.keywords
                if keyword.arg == "fixed_scale_factor"
            ),
            None,
        )
        return {
            "kind": node.args[0].value,
            "fixed_scale_factor": fixed_scale,
        }
    raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must use statically readable descriptor values")


def _collect_paddlegan_descriptor(root: Path) -> dict[str, object]:
    path = root / "backend/app/catalog/stage_descriptors.py"
    tree = _parse_python(path, root)
    assignment = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                isinstance(node.target, ast.Name)
                if isinstance(node, ast.AnnAssign)
                else len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            )
            and (node.target.id if isinstance(node, ast.AnnAssign) else node.targets[0].id)
            == "PADDLEGAN_STAGE_DESCRIPTOR"
        ),
        None,
    )
    if assignment is None:
        raise ContractParseError("could not find PADDLEGAN_STAGE_DESCRIPTOR in the neutral catalog")
    value = assignment.value
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "StageDescriptor":
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must construct StageDescriptor")
    if value.args:
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must use keyword-only StageDescriptor fields")
    descriptor = {
        keyword.arg: _static_descriptor_value(keyword.value) for keyword in value.keywords if keyword.arg is not None
    }
    if len(descriptor) != len(value.keywords):
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR may not use expanded keyword arguments")
    return descriptor


def diff_paddlegan_catalog_contract(
    backend_specs: set[str],
    factory_models: set[str],
    descriptor: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    missing_factories = backend_specs - factory_models
    extra_factories = factory_models - backend_specs
    if missing_factories or extra_factories:
        issues.append(
            "PaddleGAN VSR factory drift: "
            f"missing-factories={sorted(missing_factories)}, extra-factories={sorted(extra_factories)}"
        )
    expected_descriptor = {
        "execution_mode": "sequence",
        "requires_file_pipeline": True,
        "geometry": {"kind": "fixed_scale", "fixed_scale_factor": 4.0},
        "supported_backends": frozenset({"paddle"}),
        "factory_key": "paddlegan_vsr",
        "model_kind": "paddlegan_vsr",
    }
    if descriptor != expected_descriptor:
        issues.append(f"PaddleGAN VSR descriptor fields drift: expected={expected_descriptor!r}, actual={descriptor!r}")
    return issues


def _check_paddlegan_metadata(root: Path) -> list[str]:
    catalog = root / "backend/app/catalog/paddlegan_models.py"
    specs = _collect_python_dict_keys(read_source(catalog, root), "PADDLEGAN_VSR_SPECS")
    descriptor = _collect_paddlegan_descriptor(root)
    factory_path = root / "backend/app/algorithms/paddle/paddlegan_vsr/model_factory.py"
    factories = _collect_python_dict_keys(read_source(factory_path, root), "_MODEL_FACTORIES")
    return diff_paddlegan_catalog_contract(specs, factories, descriptor)


def _check_python_algorithm_factory_registry(root: Path) -> list[str]:
    factory_path = root / "backend/app/processing/streaming/stage_worker_factory.py"
    factory_source = read_source(factory_path, root)
    factories = _collect_python_name_registry(factory_source, "_ALGORITHM_FACTORIES")
    descriptor_path = root / "backend/app/catalog/stage_descriptors.py"
    descriptor_tree = _parse_python(descriptor_path, root)
    expected_keys: set[str] = set()
    for statement in descriptor_tree.body:
        value = statement.value if isinstance(statement, (ast.Assign, ast.AnnAssign)) else None
        if (
            not isinstance(value, ast.Call)
            or not isinstance(value.func, ast.Name)
            or value.func.id != "StageDescriptor"
        ):
            continue
        factory_keyword = next((keyword for keyword in value.keywords if keyword.arg == "factory_key"), None)
        if factory_keyword is None or not isinstance(factory_keyword.value, ast.Constant):
            raise ContractParseError("StageDescriptor factory_key must be a static string")
        factory_key = factory_keyword.value.value
        if not isinstance(factory_key, str):
            raise ContractParseError("StageDescriptor factory_key must be a static string")
        if factory_key != "filter_chain":
            expected_keys.add(factory_key)
    issues: list[str] = []
    if set(factories) != expected_keys:
        issues.append(
            "stage-worker algorithm factory registry drift: "
            f"expected-keys={sorted(expected_keys)}, actual-keys={sorted(factories)}"
        )

    tree = ast.parse(factory_source, filename=relative_path(factory_path, root))
    definitions = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_definitions = set(factories.values()) - set(definitions)
    if missing_definitions:
        issues.append(f"stage-worker factory registry references missing functions: {sorted(missing_definitions)}")
    for factory_name in sorted(set(factories.values()) & set(definitions)):
        lazy_modules = {
            node.module
            for node in ast.walk(definitions[factory_name])
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
        } | {
            alias.name
            for node in ast.walk(definitions[factory_name])
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name.startswith("app.")
        }
        if not lazy_modules:
            issues.append(f"stage-worker registered factory has no direct lazy app import: {factory_name}")
    return issues


def _decorator_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _find_unconsumed_python_boundary_fields(
    declaration_sources: dict[str, str],
    consumer_sources: dict[str, str],
) -> list[tuple[str, str, str]]:
    """Find neutral dataclass fields with no receiver-bound production read.

    Constructor keywords and test-only references are intentionally not
    consumers. A same-named attribute on an unrelated object is not a
    consumer: the lightweight resolver follows annotations, constructor and
    function return types, assignments, imports, and nested dataclass fields.
    """
    declarations: list[tuple[str, str, str]] = []
    all_sources = {**declaration_sources, **consumer_sources}
    parsed_sources = {source_path: ast.parse(text, filename=source_path) for source_path, text in all_sources.items()}
    parsed_declarations = {source_path: parsed_sources[source_path] for source_path in declaration_sources}

    class_nodes: dict[str, list[tuple[str, ast.ClassDef]]] = {}
    for source_path, tree in parsed_sources.items():
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_nodes.setdefault(node.name, []).append((source_path, node))
    # Simple names are sufficient only when unambiguous. This intentionally
    # refuses to guess between unrelated same-named classes.
    known_fields: dict[str, dict[str, str | None]] = {
        name: {} for name, owners in class_nodes.items() if len(owners) == 1
    }
    class_paths: dict[str, str] = {}

    def annotation_type(node: ast.expr | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                return annotation_type(ast.parse(node.value, mode="eval").body)
            except SyntaxError:
                return None
        if isinstance(node, ast.Name):
            return node.id if node.id in known_fields else None
        if isinstance(node, ast.Attribute):
            return node.attr if node.attr in known_fields else None
        if isinstance(node, ast.Subscript):
            candidates = node.slice.elts if isinstance(node.slice, ast.Tuple) else (node.slice,)
            for candidate in reversed(candidates):
                if resolved := annotation_type(candidate):
                    return resolved
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return annotation_type(node.left) or annotation_type(node.right)
        return None

    # Register the reportable boundary classes. Other uniquely named classes
    # remain in ``known_fields`` solely to carry receiver types through nested
    # expressions such as ``context.preflight.video_info.has_audio``.
    for source_path, tree in parsed_declarations.items():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and "dataclass" in {
                name for decorator in node.decorator_list if (name := _decorator_name(decorator)) is not None
            }:
                if node.name in class_paths:
                    raise ContractParseError(f"duplicate Python boundary class name: {node.name}")
                if node.name not in known_fields:
                    raise ContractParseError(f"ambiguous Python boundary class name: {node.name}")
                class_paths[node.name] = source_path

    for name, owners in class_nodes.items():
        if name not in known_fields:
            continue
        _source_path, node = owners[0]
        for member in node.body:
            if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                known_fields[name][member.target.id] = annotation_type(member.annotation)

    class_fields = {name: known_fields[name] for name in class_paths}

    for source_path, tree in parsed_declarations.items():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name not in class_fields:
                continue
            for member in node.body:
                if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name):
                    continue
                if member.target.id.startswith("_"):
                    continue
                declarations.append((source_path, node.name, member.target.id))

    def module_name(source_path: str) -> str:
        normalized = source_path.replace("\\", "/")
        if normalized.startswith("backend/"):
            normalized = normalized.removeprefix("backend/")
        if normalized.endswith("/__init__.py"):
            return normalized.removesuffix("/__init__.py").replace("/", ".")
        return normalized.removesuffix(".py").replace("/", ".")

    module_exports: dict[str, dict[str, str]] = {}
    for source_path, tree in parsed_sources.items():
        exports = module_exports.setdefault(module_name(source_path), {})
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in known_fields:
                exports[node.name] = node.name
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if resolved := annotation_type(node.returns):
                    exports[node.name] = resolved
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if resolved := annotation_type(node.annotation):
                    exports[node.target.id] = resolved

    consumed: set[tuple[str, str]] = set()

    class BoundaryReadVisitor(ast.NodeVisitor):
        def __init__(self, source_path: str, tree: ast.Module) -> None:
            self.source_path = source_path
            self.tree = tree
            self.module = module_name(source_path)
            self.module_env = dict(module_exports.get(self.module, {}))
            self.scopes: list[dict[str, str]] = [self.module_env]
            self.class_stack: list[str | None] = []
            self._load_imports(tree)

        @property
        def env(self) -> dict[str, str]:
            return self.scopes[-1]

        def _load_imports(self, tree: ast.Module) -> None:
            for statement in tree.body:
                if not isinstance(statement, ast.ImportFrom) or not statement.module:
                    continue
                exports = module_exports.get(statement.module, {})
                for alias in statement.names:
                    if resolved := exports.get(alias.name):
                        self.module_env[alias.asname or alias.name] = resolved

        def _lookup(self, name: str) -> str | None:
            for scope in reversed(self.scopes):
                if name in scope:
                    return scope[name]
            return name if name in known_fields else None

        def _infer(self, node: ast.expr | None) -> str | None:
            if node is None:
                return None
            if isinstance(node, ast.Name):
                return self._lookup(node.id)
            if isinstance(node, ast.Attribute):
                owner = self._infer(node.value)
                if owner and node.attr in known_fields.get(owner, {}):
                    return known_fields[owner][node.attr]
                return None
            if isinstance(node, ast.Subscript):
                return self._infer(node.value)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    return self._lookup(node.func.id)
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "items", "values"}:
                    return self._infer(node.func.value)
                return None
            if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
                return next((resolved for item in node.elts if (resolved := self._infer(item))), None)
            if isinstance(node, ast.Dict):
                return next((resolved for item in node.values if (resolved := self._infer(item))), None)
            if isinstance(node, ast.IfExp):
                return self._infer(node.body) or self._infer(node.orelse)
            return None

        def _bind(self, target: ast.expr, resolved: str | None) -> None:
            if resolved is None:
                return
            if isinstance(target, ast.Name):
                self.env[target.id] = resolved
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    self._bind(element, resolved)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            owner = node.name if node.name in known_fields else None
            self.class_stack.append(owner)
            for statement in node.body:
                self.visit(statement)
            self.class_stack.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            local = dict(self.module_env)
            arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            for argument in arguments:
                if resolved := annotation_type(argument.annotation):
                    local[argument.arg] = resolved
            if self.class_stack and self.class_stack[-1] and arguments:
                local[arguments[0].arg] = self.class_stack[-1]
            self.scopes.append(local)
            for statement in node.body:
                self.visit(statement)
            self.scopes.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
            self.visit(node.value)
            resolved = self._infer(node.value)
            for target in node.targets:
                self._bind(target, resolved)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
            if node.value is not None:
                self.visit(node.value)
            self._bind(node.target, annotation_type(node.annotation) or self._infer(node.value))

        def visit_For(self, node: ast.For) -> None:  # noqa: N802
            self.visit(node.iter)
            self._bind(node.target, self._infer(node.iter))
            for statement in (*node.body, *node.orelse):
                self.visit(statement)

        def _visit_comprehension(
            self,
            generators: list[ast.comprehension],
            values: tuple[ast.expr, ...],
        ) -> None:
            self.scopes.append(dict(self.env))
            for generator in generators:
                self.visit(generator.iter)
                self._bind(generator.target, self._infer(generator.iter))
                for condition in generator.ifs:
                    self.visit(condition)
            for value in values:
                self.visit(value)
            self.scopes.pop()

        def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.key, node.value))

        def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
            if isinstance(node.ctx, ast.Load):
                owner = self._infer(node.value)
                if owner and node.attr in class_fields.get(owner, {}):
                    consumed.add((owner, node.attr))
            self.generic_visit(node)

    for source_path, tree in parsed_sources.items():
        BoundaryReadVisitor(source_path, tree).visit(tree)

    return sorted(declaration for declaration in declarations if (declaration[1], declaration[2]) not in consumed)


def _check_python_boundary_field_consumers(root: Path) -> list[str]:
    declaration_paths = [
        *sorted((root / "backend/app/catalog").glob("*.py")),
        *sorted((root / "backend/app/ports").glob("*.py")),
    ]
    declaration_sources = {
        relative_path(path, root): read_source(path, root) for path in declaration_paths if path.name != "__init__.py"
    }
    app_root = root / "backend/app"
    consumer_sources = {
        relative_path(path, root): read_source(path, root)
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    }
    return [
        f"Python boundary field has no production consumer: {source_path} -> {owner}.{field}"
        for source_path, owner, field in _find_unconsumed_python_boundary_fields(
            declaration_sources,
            consumer_sources,
        )
    ]


def _literal_all_names(tree: ast.Module) -> set[str]:
    for statement in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if not isinstance(target, ast.Name) or target.id != "__all__" or value is None:
            continue
        try:
            names = ast.literal_eval(value)
        except (TypeError, ValueError) as exc:
            raise ContractParseError("Python package __all__ must be a literal sequence") from exc
        if not isinstance(names, (list, tuple)) or not all(isinstance(name, str) for name in names):
            raise ContractParseError("Python package __all__ must contain only literal names")
        if len(names) != len(set(names)):
            raise ContractParseError("Python package __all__ contains duplicate names")
        return set(names)
    return set()


@cache
def _parse_python_text(text: str) -> ast.Module:
    return ast.parse(text)


def _find_unconsumed_python_package_reexports(
    package_module: str,
    init_text: str,
    consumer_sources: list[str],
) -> set[str]:
    exported = _literal_all_names(ast.parse(init_text))
    consumed: set[str] = set()
    for text in consumer_sources:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != package_module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    consumed.update(exported)
                else:
                    consumed.add(alias.name)
    return exported - consumed


def _absolute_python_import_module(
    current_module: str,
    *,
    current_is_package: bool,
    imported_module: str | None,
    level: int,
) -> str:
    if level == 0:
        return imported_module or ""
    package = current_module if current_is_package else current_module.rpartition(".")[0]
    parts = package.split(".") if package else []
    ascend = level - 1
    if ascend > len(parts):
        return ""
    resolved = parts[: len(parts) - ascend]
    if imported_module:
        resolved.extend(imported_module.split("."))
    return ".".join(resolved)


def _dotted_python_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_python_name(node.value)
        return f"{owner}.{node.attr}" if owner else None
    return None


def _find_unconsumed_python_module_exports(
    module_name: str,
    module_text: str,
    consumer_modules: list[tuple[str, bool, str]],
) -> set[str]:
    """Find ordinary-module exports with no external production consumer."""
    tree = _parse_python_text(module_text)
    exported = _literal_all_names(tree)
    if not exported:
        return set()

    # Internal reads prove that the symbol is live, not that it belongs to the
    # module's public surface. Only another production module can justify an
    # ordinary-module export.
    consumed: set[str] = set()

    for consumer_module, consumer_is_package, text in consumer_modules:
        consumer_tree = _parse_python_text(text)
        module_aliases: dict[str, str] = {}
        for node in ast.walk(consumer_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    module_aliases[local_name] = alias.name if alias.asname else local_name
                continue
            if not isinstance(node, ast.ImportFrom):
                continue
            imported_from = _absolute_python_import_module(
                consumer_module,
                current_is_package=consumer_is_package,
                imported_module=node.module,
                level=node.level,
            )
            if imported_from == module_name:
                for alias in node.names:
                    if alias.name == "*":
                        consumed.update(exported)
                    elif alias.name in exported:
                        consumed.add(alias.name)
            for alias in node.names:
                candidate_module = f"{imported_from}.{alias.name}" if imported_from else alias.name
                if candidate_module == module_name:
                    module_aliases[alias.asname or alias.name] = module_name

        for node in ast.walk(consumer_tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
                continue
            dotted = _dotted_python_name(node)
            if not dotted:
                continue
            first, separator, remainder = dotted.partition(".")
            resolved = f"{module_aliases[first]}.{remainder}" if separator and first in module_aliases else dotted
            prefix = f"{module_name}."
            if resolved.startswith(prefix):
                exported_name = resolved[len(prefix) :].partition(".")[0]
                if exported_name in exported:
                    consumed.add(exported_name)

    return exported - consumed


def _check_python_package_reexports(root: Path) -> list[str]:
    app_root = root / "backend/app"
    production_paths = [
        path
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    ]
    issues: list[str] = []
    for init_path in (path for path in production_paths if path.name == "__init__.py"):
        package_module = _python_module_name(app_root, init_path)
        consumers = [read_source(path, root) for path in production_paths if path != init_path]
        issues.extend(
            f"unconsumed Python package re-export `{name}`: {relative_path(init_path, root)}"
            for name in sorted(
                _find_unconsumed_python_package_reexports(
                    package_module,
                    read_source(init_path, root),
                    consumers,
                )
            )
        )
    return issues


def _check_python_module_exports(root: Path) -> list[str]:
    app_root = root / "backend/app"
    production_paths = [
        path
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    ]
    module_sources = [
        (
            _python_module_name(app_root, path),
            path.name == "__init__.py",
            read_source(path, root),
            path,
        )
        for path in production_paths
    ]
    issues: list[str] = []
    for module_name, is_package, source, path in module_sources:
        if is_package:
            continue
        consumers = [
            (consumer_module, consumer_is_package, consumer_source)
            for consumer_module, consumer_is_package, consumer_source, consumer_path in module_sources
            if consumer_path != path
        ]
        issues.extend(
            f"Python module export has no production consumer: {relative_path(path, root)} -> {name}"
            for name in sorted(_find_unconsumed_python_module_exports(module_name, source, consumers))
        )
    return issues


def _python_module_name(app_root: Path, path: Path) -> str:
    parts = list(path.relative_to(app_root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_inert_package_statement(statement: ast.stmt, *, first: bool) -> bool:
    if first and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return isinstance(statement.value.value, str)
    return isinstance(statement, ast.ImportFrom) and statement.module == "__future__"


def _check_side_effect_free_python_packages(root: Path) -> list[str]:
    paths = (
        "backend/app/__init__.py",
        "backend/app/algorithms/__init__.py",
        "backend/app/algorithms/paddle/__init__.py",
        "backend/app/algorithms/pytorch/__init__.py",
        "backend/app/cli/__init__.py",
        "backend/app/cli/commands/__init__.py",
        "backend/app/processing/__init__.py",
    )
    issues: list[str] = []
    for relative in paths:
        path = root / relative
        tree = _parse_python(path, root)
        for index, statement in enumerate(tree.body):
            if not _is_inert_package_statement(statement, first=index == 0):
                issues.append(
                    f"side-effect-free Python package executes top-level {statement.__class__.__name__}: "
                    f"{relative}:{statement.lineno}"
                )
    return issues


def _literal_handler_registry(tree: ast.Module) -> dict[str, tuple[str, str]]:
    return literal_string_pair_registry(tree, "_HANDLERS")


def _check_python_cli_commands(root: Path) -> list[str]:
    main_path = root / "backend/app/cli/main.py"
    parser_path = root / "backend/app/cli/parser.py"
    main_tree = _parse_python(main_path, root)
    parser_tree = _parse_python(parser_path, root)
    registry = _literal_handler_registry(main_tree)
    manifest = json.loads(read_source(root / "contracts/ipc-manifest.json", root))
    generated_command_constants = {
        "STAGE_WORKER_SUBCOMMAND": manifest["stageWorkerCommand"]["subcommand"],
    }
    parser_handlers: set[str] = set()
    parser_commands: set[str] = set()
    for node in ast.walk(parser_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "add_parser" and node.args:
            command = node.args[0]
            if isinstance(command, ast.Constant) and isinstance(command.value, str):
                parser_commands.add(command.value)
            elif isinstance(command, ast.Name) and command.id in generated_command_constants:
                parser_commands.add(generated_command_constants[command.id])
        if node.func.attr == "set_defaults":
            for keyword in node.keywords:
                if keyword.arg == "handler" and isinstance(keyword.value, ast.Constant):
                    if not isinstance(keyword.value.value, str):
                        raise ContractParseError("CLI parser handler identifiers must be literal strings")
                    parser_handlers.add(keyword.value.value)

    issues: list[str] = []
    registry_keys = set(registry)
    if parser_handlers != registry_keys:
        issues.append(
            "Python CLI handler registry drift: "
            f"only-in-parser={sorted(parser_handlers - registry_keys)}, "
            f"only-in-registry={sorted(registry_keys - parser_handlers)}"
        )
    normalized_handlers = {handler.replace("_", "-") for handler in parser_handlers}
    if normalized_handlers != parser_commands:
        issues.append(
            "Python CLI parser command reachability drift: "
            f"without-handler={sorted(parser_commands - normalized_handlers)}, "
            f"without-command={sorted(normalized_handlers - parser_commands)}"
        )

    command_root = root / "backend/app/cli/commands"
    implementations: set[tuple[str, str]] = set()
    for path in sorted(command_root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = _python_module_name(root / "backend/app", path)
        tree = _parse_python(path, root)
        implementations.update(
            (module, statement.name)
            for statement in tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name.startswith("cmd_")
        )
    registered_targets = set(registry.values())
    if registered_targets != implementations:
        issues.append(
            "Python CLI command implementation reachability drift: "
            f"unregistered={sorted(implementations - registered_targets)}, "
            f"missing={sorted(registered_targets - implementations)}"
        )

    eager_command_imports = sorted(
        {
            imported
            for node in main_tree.body
            for imported in (
                ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                + ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            )
            if imported.startswith("app.cli.commands")
        }
    )
    if eager_command_imports:
        issues.append(f"Python CLI command modules must be imported lazily: {eager_command_imports}")

    backend_subcommands = {
        manifest["backendProcessCommand"]["subcommand"],
        *(entry["subcommand"] for entry in manifest["backendOneShotCommands"]),
        manifest["stageWorkerCommand"]["subcommand"],
    }
    if not backend_subcommands <= parser_commands:
        issues.append(
            f"IPC backend subcommands are unreachable from Python CLI: {sorted(backend_subcommands - parser_commands)}"
        )
    return issues


def _check_typed_ndjson_error_emission(root: Path) -> list[str]:
    path = root / "backend/app/__main__.py"
    manual_error_envelopes = re.findall(r"[\"']type[\"']\s*:\s*[\"']error[\"']", read_source(path, root))
    if len(manual_error_envelopes) != 1:
        return [
            f"normal CLI failures must keep only the bootstrap manual error envelope in {relative_path(path, root)}"
        ]
    return []


def _check_backend_package_cycles(root: Path) -> list[str]:
    app_root = root / "backend/app"
    edges: dict[str, set[str]] = {}
    for path in sorted(app_root.rglob("*.py")):
        relative_parts = path.relative_to(app_root).parts
        if "vendor" in relative_parts or path.name.startswith("ifnet_v4_"):
            continue
        source = relative_parts[0].removesuffix(".py")
        tree = _parse_python(path, root)
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            imports = ([module] if module else []) + names
            for imported in imports:
                if not imported.startswith("app."):
                    continue
                target = imported.split(".", 2)[1]
                if target != source:
                    edges.setdefault(source, set()).add(target)

    return [
        f"backend package dependency cycle: {' -> '.join((*cycle, cycle[0]))}"
        for cycle in _find_dependency_cycles(edges)
    ]
