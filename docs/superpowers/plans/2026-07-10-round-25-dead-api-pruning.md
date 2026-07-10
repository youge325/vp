# VP Workbench Round 25 Dead API Pruning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove test-only and unreachable frontend/backend production APIs while preserving runtime behavior.

**Architecture:** Keep real owners and runtime call paths intact. Tests stop importing implementation-only symbols, FFmpeg command rules remain in focused submodules, and architecture contracts prevent deleted surfaces from returning.

**Tech Stack:** Vue 3, TypeScript 6, Vitest, Python 3.12, pytest, Ruff.

## Global Constraints

- Do not change UI, IPC commands, CLI arguments, TaskRequest, NDJSON events, preset payloads, or processing behavior.
- Do not add dependencies, branches, or pull requests.
- Commit and push directly to `main` only after all verification gates pass.

---

### Task 1: Establish RED architecture contracts

**Files:**
- Modify: `backend/tests/test_architecture_contracts.py`
- Modify: `scripts/check_architecture_contracts.py`

- [ ] Add current-state assertions for the frontend `InvokeError` export and the identified backend dead APIs.
- [ ] Extend the synthetic dead-surface checker test with representative forbidden definitions.
- [ ] Run the focused architecture tests and confirm failures against current production sources.

### Task 2: Privatize the frontend IPC error type

**Files:**
- Modify: `frontend/src/lib/ipc/client.ts`
- Create: `frontend/src/composables/app/__tests__/errors.ts`
- Modify: `frontend/src/composables/app/__tests__/useMediaImport.spec.ts`
- Modify: `frontend/src/composables/app/__tests__/useOutputPicker.spec.ts`
- Modify: `frontend/src/composables/app/__tests__/usePresetSync.spec.ts`

- [ ] Add a test-only coded-error factory with the same structural error shape consumed by `normalizeError()`.
- [ ] Replace test imports and constructions of `InvokeError` with the test helper.
- [ ] Remove `export` from `InvokeError` and run the three focused composable specs.

### Task 3: Remove backend dead API surfaces

**Files:**
- Modify: `backend/app/algorithms/factory.py`
- Modify: `backend/app/algorithms/tensor_backend.py`
- Modify: `backend/app/utils/ffmpeg/__init__.py`
- Modify: `backend/app/utils/ffmpeg/encode.py`
- Modify: `backend/app/processing/streaming/encoder_segment_writer.py`
- Modify: `backend/app/algorithms/paddle/paddlegan_vsr/vendor/ppgan/modules/init.py`
- Modify: `backend/tests/test_algorithms/test_factory.py`
- Modify: `backend/tests/test_algorithms/test_interpolation.py`
- Modify: `backend/tests/test_utils/test_ffmpeg/test_wrapper.py`
- Create: `backend/tests/test_utils/test_ffmpeg/test_io.py`

- [ ] Remove test-only factory registry inspection and redundant registration-only tests.
- [ ] Remove unused tensor backend capability methods from the interface and implementations.
- [ ] Move raw command-builder coverage to the owning I/O module, then remove wrapper forwarding methods and dead format conversion.
- [ ] Remove unreferenced segment-writer accessors and PaddleGAN initializers.
- [ ] Run the focused backend tests.

### Task 4: Complete GREEN and publish

- [ ] Finish the architecture checker implementation and run `python scripts/check_architecture_contracts.py`.
- [ ] Run `cd backend; python -m pytest tests/test_architecture_contracts.py -q`.
- [ ] Run `cd frontend; npm run build`.
- [ ] Run `pre-commit run --all-files`.
- [ ] Review `git diff --check` and `git status --short`.
- [ ] Commit the focused changes and push `main`.
- [ ] Re-run the symbol-reference audit to select the next batch without marking the long-running goal complete.
