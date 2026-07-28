"""Small, invariant-based architecture rules.

Historical one-off tombstones do not belong here.  Rules in this catalog
describe dependency direction or a compatibility boundary that remains true
for the current architecture.
"""

from __future__ import annotations

from .rules import AbsentPathRule, ForbiddenReferenceRule


def _refs(
    rule_id: str,
    roots: tuple[str, ...],
    patterns: tuple[str, ...],
    message: str,
    *,
    suffixes: tuple[str, ...],
) -> ForbiddenReferenceRule:
    return ForbiddenReferenceRule(rule_id, roots, patterns, message, suffixes)


RULES = (
    AbsentPathRule(
        "frontend-tests-outside-test-tree",
        "frontend/src/__tests__",
        "frontend unit tests must live under frontend/tests/unit",
    ),
    _refs(
        "frontend-services-are-framework-free",
        ("frontend/src/services",),
        (
            r"from\s+['\"](?:vue|pinia|@tauri-apps/)",
            r"from\s+['\"]@/(?:stores|composables|components|views)(?:/|['\"])",
        ),
        "frontend service depends on a framework or upper layer",
        suffixes=(".ts", ".tsx", ".vue"),
    ),
    _refs(
        "frontend-stores-do-not-orchestrate-ipc",
        ("frontend/src/stores",),
        (
            r"from\s+['\"]@/(?:lib/ipc|composables|components|views)(?:/|['\"])",
            r"from\s+['\"]@tauri-apps/",
            r"\bsafeInvoke\s*\(",
        ),
        "frontend store bypasses the service/application boundary",
        suffixes=(".ts", ".tsx", ".vue"),
    ),
    _refs(
        "frontend-ipc-is-a-leaf-adapter",
        ("frontend/src/lib/ipc",),
        (r"from\s+['\"]@/(?:services|stores|composables|components|views)(?:/|['\"])",),
        "frontend IPC adapter depends on an upper layer",
        suffixes=(".ts", ".tsx"),
    ),
    _refs(
        "backend-protocol-is-a-leaf",
        ("backend/app/protocol",),
        (r"(?:from|import)\s+app\.(?:algorithms|cli|planning|processing|utils)\b",),
        "backend protocol layer depends on application or infrastructure code",
        suffixes=(".py",),
    ),
    _refs(
        "backend-utils-do-not-depend-on-algorithms",
        ("backend/app/utils",),
        (r"(?:from|import)\s+app\.algorithms\b",),
        "backend utility layer depends on algorithms and creates a package cycle",
        suffixes=(".py",),
    ),
)
