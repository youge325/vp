# VP Workbench Round 22 Architecture Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove redundant frontend workflow forwarding and isolate backend manifest persistence while preserving all existing behavior and import paths.

**Architecture:** Keep `enhance-workflow.ts` and `SegmentManifest` as stable facades. Replace frontend pass-through functions with export aliases, and delegate backend JSON persistence to a focused internal store module.

**Tech Stack:** Vue 3, TypeScript 6, Vitest, Python 3.12, pytest, Ruff.

## Global Constraints

- Do not change UI, IPC commands, TaskRequest, NDJSON events, preset wire shape, or processing semantics.
- Do not add dependencies or create a branch/PR.
- Work directly on `main`, then commit and push only after verification passes.

---

### Task 1: Remove frontend pass-through wrappers

**Files:**
- Modify: `frontend/src/services/preset/enhance-workflow.ts`
- Modify: `frontend/src/services/preset/enhance-workflow.spec.ts`

**Interfaces:**
- Consumes: the four `*SelectionDefaults` functions from `enhance-workflow-selection.ts`.
- Produces: the existing `apply*Selection` exports with unchanged signatures.

- [ ] Add a test asserting each public selection export is the same function reference as its defaults implementation.
- [ ] Run `cd frontend; npm run test -- src/services/preset/enhance-workflow.spec.ts` and confirm the identity assertion fails against the wrappers.
- [ ] Replace the four wrapper bodies with named export aliases; retain enabled/scale/frame mutation functions.
- [ ] Re-run the targeted test and confirm it passes.

### Task 2: Extract manifest persistence

**Files:**
- Create: `backend/app/planning/manifest_store.py`
- Create: `backend/tests/test_processing/test_manifest_store.py`
- Modify: `backend/app/planning/manifest.py`
- Modify: `backend/tests/test_processing/test_segment_manifest.py`

**Interfaces:**
- Produces: `MANIFEST_VERSION`, `load_manifest(path)`, and `write_manifest(path, *, signature, output_path, config_snapshot)`.
- Preserves: `SegmentManifest.MANIFEST_VERSION`, `prepare()`, `inspect()`, and public dataclasses.

- [ ] Add store tests for version rejection and atomic `.tmp` replacement.
- [ ] Run the new test file and confirm import failure because `manifest_store` does not exist.
- [ ] Implement the store module with the current serialization and validation behavior.
- [ ] Delegate `SegmentManifest` persistence calls to the store and remove local JSON/timestamp helpers.
- [ ] Move the existing atomic-write monkeypatch to `manifest_store.os.replace` and run both manifest test files.

### Task 3: Protect architecture boundaries

**Files:**
- Modify: `scripts/check_architecture_contracts.py`
- Modify: `backend/tests/test_architecture_contracts.py`

**Interfaces:**
- Produces: checks that reject frontend forwarding function bodies and backend manifest persistence leakage.

- [ ] Add failing contract tests using temporary source files containing a wrapper body or local JSON persistence helper.
- [ ] Run the focused architecture tests and confirm the new expectations fail.
- [ ] Add contract checks and wire them into `main()`.
- [ ] Run `python scripts/check_architecture_contracts.py` and `cd backend; python -m pytest tests/test_architecture_contracts.py -q`.

### Task 4: Verify and publish

**Files:**
- Modify: `docs/04-backend-architecture.md`
- Modify: `docs/09-resume-checkpointing.md`

**Interfaces:**
- Documents the new persistence owner while keeping `SegmentManifest` as the lifecycle facade.

- [ ] Update the two architecture references.
- [ ] Run targeted frontend/backend tests.
- [ ] Run `cd frontend; npm run build`.
- [ ] Run `pre-commit run --all-files`.
- [ ] Review `git diff --check` and `git status --short`.
- [ ] Commit with `Slim workflow and manifest persistence boundaries` and push `main`.
