# VP Workbench Round 29 Write-Only State Pruning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove confirmed write-only Anime/RIFE state and zero-call RIFE properties.

**Architecture:** Constructors retain only state used by runtime behavior. Tests observe public processing results rather than private dormant fields.

**Tech Stack:** Python 3.12, PyTorch, ONNX Runtime, pytest, Ruff.

## Global Constraints

- Preserve algorithm factory kwargs, model loading, inference output, CLI/IPC/NDJSON contracts, and UI behavior.
- Run PyTorch tests separately from Paddle tests.
- Add no dependencies, branches, or pull requests; commit and push directly to `main` after verification.

---

### Task 1: Establish RED

**Files:**
- Modify: `backend/tests/test_processing/test_anime_optimization.py`
- Modify: `backend/tests/test_architecture_contracts.py`

- [x] Replace private-field assertions with constructor/identity behavior coverage.
- [x] Assert removed Anime and RIFE fields/properties are absent.
- [x] Add a synthetic architecture-checker test and observe expected failures.

### Task 2: Prune Runtime State

**Files:**
- Modify: `backend/app/processing/anime_optimization.py`
- Modify: `backend/app/algorithms/pytorch/rife/solver.py`
- Modify: `backend/app/algorithms/pytorch/rife/onnx_solver.py`

- [x] Stop storing Anime factory kwargs.
- [x] Make RIFE model config local and retain only inference state.
- [x] Remove abandoned padding/encode caches and constructor copies.
- [x] Remove zero-call RIFE properties and ONNX model-version copy.

### Task 3: Protect And Verify

**Files:**
- Modify: `scripts/check_architecture_contracts.py`
- Modify: architecture contract tests

- [x] Add production and synthetic write-only-state guards.
- [x] Run Anime, RIFE solver/ONNX, architecture, and schema tests.
- [x] Run frontend build, architecture scripts, and pre-commit.

### Task 4: Review And Publish

- [x] Review retained state, references, and `git diff --check`.
- [x] Commit and push `main`.
- [x] Re-run write-only state, exports, module reachability, duplicates, and zero-reference audits.
