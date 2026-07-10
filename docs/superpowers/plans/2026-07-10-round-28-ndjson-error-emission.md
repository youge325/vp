# VP Workbench Round 28 NDJSON Error Emission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make typed NDJSON error emission the normal runtime path and remove unused emitter singleton state.

**Architecture:** `app.__main__` retains one import-safe fallback helper. Once application imports succeed, protocol payload ownership stays in `app.protocol`.

**Tech Stack:** Python 3.12, Pydantic 2, pytest, Ruff.

## Global Constraints

- Preserve TaskErrorCode values, NDJSON event names, payload fields, process exit codes, and Tauri behavior.
- Keep bootstrap emission independent of protocol imports.
- Add no dependencies, branches, or pull requests; commit and push directly to `main` after verification.

---

### Task 1: Establish RED

**Files:**
- Add: `backend/tests/test_protocol/test_main_error_emission.py`
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Verify `ProcessError` is routed through `ndjson.error()`.
- [x] Verify unexpected exceptions are normalized and routed through `ndjson.error()`.
- [x] Assert the protocol emitter has no public class or singleton state.
- [x] Add a synthetic architecture-checker test and observe expected failures.

### Task 2: Implement Runtime Cleanup

**Files:**
- Modify: `backend/app/__main__.py`
- Modify: `backend/app/protocol/__init__.py`

- [x] Add one local import-safe error-envelope fallback helper.
- [x] Import `ndjson` only after CLI/application imports succeed.
- [x] Route normal structured and unexpected errors through the typed emitter.
- [x] Make the emitter implementation private and remove `_instance`/`__new__`.

### Task 3: Protect And Verify

**Files:**
- Modify: `scripts/check_architecture_contracts.py`
- Modify: architecture contract tests

- [x] Guard emitter lifecycle and normal error routing boundaries.
- [x] Run protocol, error-code, CLI envelope integration, schema drift, and architecture tests.
- [x] Run the architecture scripts, frontend build, and pre-commit.

### Task 4: Review And Publish

- [x] Review bootstrap independence, serialized envelopes, and `git diff --check`.
- [x] Commit and push `main`.
- [x] Re-run final exported-symbol, module-reachability, duplicate-body, and zero-reference audits.
