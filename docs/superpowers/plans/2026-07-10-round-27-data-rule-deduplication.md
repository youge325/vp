# VP Workbench Round 27 Data Rule Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give finite-number coercion, camelCase aliases, and RIFE model metadata one owner each, then delete one unreachable vendor module.

**Architecture:** Shared frontend scalar rules live in a domain-neutral service. Pydantic owns alias conversion. Typed `RifeModelSpec` data remains the only global RIFE metadata representation.

**Tech Stack:** Vue 3, TypeScript 6, Vitest, Python 3.12, Pydantic 2, pytest, Ruff.

## Global Constraints

- Preserve UI, IPC, CLI, TaskRequest, NDJSON events, preset payloads, and processing behavior.
- Preserve RIFE model coverage and `load_rife_model()`'s config-dict return shape.
- Add no dependencies, branches, or pull requests; commit and push directly to `main` after verification.

---

### Task 1: Establish frontend RED

**Files:**
- Add: `frontend/src/services/finite-number.spec.ts`
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Specify finite, absent, `NaN`, and infinite input behavior for `finiteNumberOrNull()`.
- [x] Assert metric services do not define their own finite-number normalizer.
- [x] Run focused tests and observe the missing shared module failure.

### Task 2: Establish backend RED

**Files:**
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Assert config and payload models use Pydantic's camel alias generator without private copies.
- [x] Assert RIFE metadata no longer defines or imports `MODEL_CONFIGS`.
- [x] Assert the unused PaddleGAN vendor logger module is absent.
- [x] Add a synthetic architecture-checker test and observe all expected issue classes.

### Task 3: Implement shared data rules

**Files:**
- Add: `frontend/src/services/finite-number.ts`
- Modify: frontend metric services
- Modify: backend model and payload modules
- Modify: RIFE spec, ONNX runtime/export, and tests
- Delete: `backend/app/algorithms/paddle/paddlegan_vsr/vendor/ppgan/utils/logger.py`

- [x] Route both frontend consumers through `finiteNumberOrNull()` and remove repeated coercion.
- [x] Replace both private camel converters with `pydantic.alias_generators.to_camel`.
- [x] Migrate RIFE consumers and tests to typed specs, then remove the legacy global dictionary.
- [x] Delete the unreachable vendor logger module.

### Task 4: Protect and verify

**Files:**
- Modify: `scripts/check_architecture_contracts.py`
- Modify: architecture contract tests

- [x] Add production and synthetic guards for all four boundaries.
- [x] Run focused frontend, schema/protocol, PyTorch RIFE, and PaddleGAN tests in isolated processes.
- [x] Run the full frontend suite, production build, architecture checker, and pre-commit.

### Task 5: Review and publish

- [x] Review references, generated/wire stability, and `git diff --check`.
- [x] Commit and push `main`.
- [x] Re-run exported-symbol, module-reachability, duplicate-body, and zero-reference audits.
