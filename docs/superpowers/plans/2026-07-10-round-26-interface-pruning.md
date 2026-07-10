# VP Workbench Round 26 Interface Pruning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate duplicate frontend number coercion and remove backend interfaces with no production caller.

**Architecture:** Shared option coercion belongs to `preset/options.ts`. Backend strategy and metrics classes expose only methods exercised by current runtime paths, while compatibility payload keys remain stable.

**Tech Stack:** Vue 3, TypeScript 6, Vitest, Python 3.12, pytest, Ruff.

## Global Constraints

- Preserve UI, IPC, CLI, TaskRequest, NDJSON events, preset payloads, and processing behavior.
- Preserve `stageDurationsSeconds` in metrics snapshots.
- Add no dependencies, branches, or pull requests; commit and push directly to `main` after verification.

---

### Task 1: Establish frontend RED

**Files:**
- Modify: `frontend/src/services/preset/options.spec.ts`
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Import and specify `toNumberValue()` in the shared options spec.
- [x] Add architecture assertions forbidding numeric converters in `enhance-options.ts` and `io-options.ts`.
- [x] Run both focused tests and confirm failures against current ownership.

### Task 2: Establish backend RED

**Files:**
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Assert the algorithm base and implementations no longer define test-only batch/validation/description methods.
- [x] Assert RIFE solvers, PaddleGAN MSVSR, and metrics no longer define zero-reference methods or duration state.
- [x] Extend the synthetic dead-surface checker and observe expected failures.

### Task 3: Consolidate frontend conversion

**Files:**
- Modify: `frontend/src/services/preset/options.ts`
- Modify: `frontend/src/services/preset/enhance-options.ts`
- Modify: `frontend/src/services/preset/io-options.ts`
- Modify: `frontend/src/composables/forms/enhance-option-setters.ts`
- Modify: `frontend/src/composables/forms/encode-output-state.ts`
- Modify: `frontend/src/composables/forms/encode-rate-control-bindings.ts`
- Modify: related specs

- [x] Add the shared converter and update all consumers.
- [x] Remove duplicate specialized converters and move their assertions to the shared owner.
- [x] Run preset and binding tests.

### Task 4: Narrow backend runtime interfaces

**Files:**
- Modify: `backend/app/algorithms/base.py`
- Modify: concrete algorithm modules and tests
- Modify: both RIFE solver modules and ONNX tests
- Modify: PaddleGAN MSVSR vendor module
- Modify: `backend/app/processing/streaming/metrics.py` and metrics tests

- [x] Remove the unused algorithm interface methods and concrete overrides.
- [x] Remove zero-reference solver and flow methods.
- [x] Remove metrics timing APIs/state while preserving the snapshot key.
- [x] Run non-Paddle and Paddle tests in separate processes.

### Task 5: Protect, verify, and publish

- [x] Implement architecture checker rules and run its pytest suite.
- [x] Run the frontend full unit suite and production build.
- [x] Run `python scripts/check_architecture_contracts.py` and `pre-commit run --all-files`.
- [x] Review `git diff --check`, commit, and push `main`.
- [x] Re-run reference and forwarding audits for the next batch.
