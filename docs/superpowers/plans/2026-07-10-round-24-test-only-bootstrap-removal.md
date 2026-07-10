# VP Workbench Round 24 Test-Only Bootstrap Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete a test-only global algorithm bootstrap from production and move test registry setup to pytest.

**Architecture:** Stage workers remain the only production registration owner. Tests explicitly establish their own registry state.

**Tech Stack:** Python 3.12, pytest, Ruff.

## Global Constraints

- Preserve CLI, stage-worker config, processing behavior, IPC, and event payloads.
- Add no dependencies or branches; push verified commits directly to `main`.

---

### Task 1: Establish RED

- [ ] Add an architecture test forbidding `register_default_algorithms` in production.
- [ ] Extend the empty-registry test to require the new caller-owned registration message.
- [ ] Run both tests and observe failures caused by current production code.

### Task 2: Move registration to tests

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_algorithms/test_factory.py`

- [ ] Register concrete test algorithms directly in the session fixture.
- [ ] Remove the production-bootstrap unit test.

### Task 3: Delete production bootstrap

**Files:**
- Modify: `backend/app/processing/__init__.py`
- Modify: `backend/app/algorithms/factory.py`
- Modify: `backend/tests/test_cli.py`
- Modify: `scripts/check_architecture_contracts.py`
- Modify: `backend/tests/test_architecture_contracts.py`

- [ ] Remove imports/function and stale startup text.
- [ ] Update the factory invariant message and CLI test.
- [ ] Extend the dead-surface architecture checker.

### Task 4: Verify and publish

- [ ] Run factory, interpolation, stage-worker, CLI, and architecture tests.
- [ ] Run the standalone architecture checker and pre-commit.
- [ ] Commit, push `main`, and continue the dead-code audit.
