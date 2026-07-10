# VP Workbench Round 23 Dead Surface Pruning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove compile-only pseudo-exports, an unreachable disabled-model path, and unused package re-exports without changing behavior.

**Architecture:** Preserve each real owner and direct import path. Delete facade and registry state that has no current consumer, then protect the narrower surfaces with repository architecture contracts.

**Tech Stack:** Vue 3, TypeScript 6, Python 3.12, Vitest/vue-tsc, pytest, Ruff.

## Global Constraints

- Do not change UI, IPC, CLI, TaskRequest, NDJSON events, preset payloads, or processing behavior.
- Do not add dependencies, branches, or pull requests.
- Commit and push directly to `main` after all gates pass.

---

### Task 1: Add failing dead-surface contracts

**Files:**
- Modify: `backend/tests/test_architecture_contracts.py`
- Modify: `scripts/check_architecture_contracts.py`

- [ ] Add current-state and fake-source tests for frontend contract exports, PaddleGAN disabled state, and dead package facades.
- [ ] Run the focused tests and confirm they fail against the current sources.
- [ ] Add checker constants/functions only after RED is observed.

### Task 2: Remove frontend pseudo-exports

**Files:**
- Modify: `frontend/src/types/protocol/_contract_check.ts`

- [ ] Remove `export` from all six contract constants and add explicit local `void` consumption.
- [ ] Run the focused architecture test and `npm run build`.

### Task 3: Remove backend disabled-model state

**Files:**
- Modify: `backend/app/algorithms/paddle/paddlegan_vsr/weights.py`
- Modify: `backend/app/planning/workflow_validation.py`
- Modify: `backend/tests/test_algorithms/test_paddlegan_vsr_specs.py`
- Modify: `scripts/check_architecture_contracts.py`
- Modify: `backend/tests/test_architecture_contracts.py`

- [ ] Delete the empty registry and unreachable validation branch.
- [ ] Simplify the PaddleGAN contract to enabled specs plus algorithm metadata.
- [ ] Run PaddleGAN spec, planning, and architecture tests.

### Task 4: Remove dead package re-exports

**Files:**
- Modify: `backend/app/benchmark/__init__.py`
- Modify: `backend/app/algorithms/paddle/paddlegan_vsr/__init__.py`

- [ ] Delete imports and `__all__` declarations with no repository consumers.
- [ ] Run benchmark, PaddleGAN, and architecture tests.

### Task 5: Verify and publish

- [ ] Run `python scripts/check_architecture_contracts.py`.
- [ ] Run `cd frontend; npm run build`.
- [ ] Run targeted frontend/backend tests.
- [ ] Run `pre-commit run --all-files`.
- [ ] Review status/diff, commit focused changes, push `main`, and repeat the low-reference audit.
