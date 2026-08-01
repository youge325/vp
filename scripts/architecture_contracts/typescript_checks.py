"""TypeScript/Vue production-consumer, test, and CSS checks."""

from __future__ import annotations

import re
from pathlib import Path

from .graph_ast import _split_top_level_commas
from .rules import read_source, relative_path


def _is_frontend_test(path: Path) -> bool:
    return path.name.endswith(".spec.ts") or "__tests__" in path.parts or "tests" in path.parts


def _check_frontend_test_layout(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    issues: list[str] = []
    for path in sorted(frontend_src.rglob("*")):
        if path.is_file() and path.name.endswith(".spec.ts"):
            issues.append(f"frontend unit test outside tests/unit: {relative_path(path, root)}")
        elif path.is_dir() and path.name == "__tests__":
            issues.append(f"frontend __tests__ directory outside tests/unit: {relative_path(path, root)}")
    return issues


def _check_frontend_dependency_boundaries(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    issues: list[str] = []
    generated_allowed = (frontend_src / "types/protocol", frontend_src / "types/generated")
    for path in sorted(frontend_src.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".vue"} or _is_frontend_test(path):
            continue
        text = read_source(path, root)
        if not any(allowed == path.parent or allowed in path.parents for allowed in generated_allowed):
            if "@/types/generated/" in text:
                issues.append(f"generated type deep import outside protocol layer: {relative_path(path, root)}")
            if "@/types/protocol/" in text:
                issues.append(f"protocol submodule import outside protocol layer: {relative_path(path, root)}")

    for relative_root in ("frontend/src/views", "frontend/src/components"):
        for path in sorted((root / relative_root).rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".vue"} or _is_frontend_test(path):
                continue
            text = read_source(path, root)
            if any(marker in text for marker in ("@/lib/ipc", "@tauri-apps/api", "safeInvoke(")):
                issues.append(f"direct IPC access in UI/store layer: {relative_path(path, root)}")
    return issues


def _find_unconsumed_protocol_reexports(index_text: str, consumer_texts: list[str]) -> set[str]:
    reexports = set(
        re.findall(
            r"^\s*export\s+type\s*\{\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\}\s+from\b",
            index_text,
            re.MULTILINE,
        )
    )
    imported: set[str] = set()
    import_pattern = re.compile(
        r"import(?:\s+type)?\s*\{(?P<body>[^}]*)\}\s*from\s*['\"]"
        r"(?:@/types/protocol|(?:\.\./)+protocol|\./index)['\"]",
    )
    for text in consumer_texts:
        for match in import_pattern.finditer(text):
            for entry in _split_top_level_commas(match.group("body")):
                name = entry.strip().removeprefix("type ").split(" as ", 1)[0].strip()
                if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name):
                    imported.add(name)
    return reexports - imported


def _check_frontend_protocol_reexports(root: Path) -> list[str]:
    protocol_root = root / "frontend/src/types/protocol"
    protocol_paths = [protocol_root / name for name in ("index.ts", "events.ts", "errors.ts")]
    frontend_src = root / "frontend/src"
    consumer_texts = [
        read_source(path, root)
        for path in sorted(frontend_src.rglob("*"))
        if path.is_file()
        and path.suffix in {".ts", ".tsx", ".vue"}
        and path not in protocol_paths
        and "generated" not in path.parts
    ]
    issues: list[str] = []
    for path in protocol_paths:
        issues.extend(
            f"unconsumed frontend protocol re-export `{name}`: {relative_path(path, root)}"
            for name in sorted(_find_unconsumed_protocol_reexports(read_source(path, root), consumer_texts))
        )
    return issues


def _find_unreferenced_css_classes(css_text: str, consumer_texts: list[str]) -> set[str]:
    classes = set(re.findall(r"\.([A-Za-z_-][A-Za-z0-9_-]*)", css_text))
    consumer_text = "\n".join(consumer_texts)
    return {
        class_name
        for class_name in classes
        if not re.search(rf"(?<![A-Za-z0-9_-]){re.escape(class_name)}(?![A-Za-z0-9_-])", consumer_text)
    }


def _find_unused_css_custom_properties(css_text: str, consumer_texts: list[str]) -> set[str]:
    properties = set(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", css_text))
    consumers = "\n".join(consumer_texts)
    return {
        property_name
        for property_name in properties
        if not re.search(rf"var\(\s*{re.escape(property_name)}(?:\s*[,)]|\s+)", consumers)
    }


def _check_frontend_global_css_classes(root: Path) -> list[str]:
    css_path = root / "frontend/src/style.css"
    frontend_src = root / "frontend/src"
    consumers = [
        read_source(path, root)
        for path in sorted(frontend_src.rglob("*"))
        if path.is_file() and path.suffix in {".ts", ".tsx", ".vue"}
    ]
    issues = [
        f"unreferenced global CSS class `.{class_name}`: frontend/src/style.css"
        for class_name in sorted(_find_unreferenced_css_classes(read_source(css_path, root), consumers))
    ]
    issues.extend(
        f"unused global CSS custom property `{property_name}`: frontend/src/style.css"
        for property_name in sorted(
            _find_unused_css_custom_properties(read_source(css_path, root), [read_source(css_path, root), *consumers])
        )
    )
    return issues


def _find_unconsumed_test_ids(source_texts: list[str], test_texts: list[str]) -> set[str]:
    test_ids = {
        test_id for text in source_texts for test_id in re.findall(r"data-testid\s*=\s*['\"]([^'\"]+)['\"]", text)
    }
    tests = "\n".join(test_texts)
    return {test_id for test_id in test_ids if test_id not in tests}


def _check_frontend_test_ids(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    frontend_tests = root / "frontend/tests"
    source_texts = [read_source(path, root) for path in sorted(frontend_src.rglob("*.vue"))]
    test_texts = [
        read_source(path, root)
        for path in sorted(frontend_tests.rglob("*"))
        if path.is_file() and path.suffix in {".ts", ".tsx", ".vue"}
    ]
    return [
        f"unconsumed frontend data-testid `{test_id}`"
        for test_id in sorted(_find_unconsumed_test_ids(source_texts, test_texts))
    ]


def _find_unconsumed_test_support_exports(sources: dict[str, str]) -> list[tuple[str, str]]:
    declaration = re.compile(
        r"^export\s+(?:declare\s+)?(?:async\s+)?"
        r"(?:interface|type|class|function|const|let|var|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        re.MULTILINE,
    )
    issues: list[tuple[str, str]] = []
    for source_path, text in sources.items():
        if source_path.endswith(".spec.ts"):
            continue
        for name in declaration.findall(text):
            pattern = re.compile(rf"\b{re.escape(name)}\b")
            if not any(pattern.search(other_text) for path, other_text in sources.items() if path != source_path):
                issues.append((source_path, name))
    return issues


def _check_frontend_test_support_exports(root: Path) -> list[str]:
    frontend_tests = root / "frontend/tests"
    sources = {relative_path(path, root): read_source(path, root) for path in sorted(frontend_tests.rglob("*.ts"))}
    return [
        f"unconsumed frontend test support export `{name}`: {source_path}"
        for source_path, name in _find_unconsumed_test_support_exports(sources)
    ]
