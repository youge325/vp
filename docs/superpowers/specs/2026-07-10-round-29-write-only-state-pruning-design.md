# VP Workbench Round 29 Write-Only State Pruning Design

## Goal

Delete instance state that is assigned but never read, plus RIFE solver properties with no caller, without changing constructor acceptance, model loading, interpolation, caching, or output values.

## Anime Placeholder

`AnimeOptimizationAlgorithm` is intentionally an identity placeholder. Its `_tensor_backend` and `_duplicate_threshold` fields are written only by `__init__` and read only by tests. Keep accepting arbitrary factory kwargs so stage construction remains compatible, but do not retain values that have no runtime behavior.

Tests continue protecting identity processing, capability profiles, stable stage naming, and constructor acceptance. They stop treating private unused fields as a contract.

## RIFE Solvers

The PyTorch solver keeps only state used during inference:

- model modules, device/dtype, modulo/head mode
- grid/flow caches keyed by padded size

Remove write-only copies of constructor parameters, unused config/channel/padding fields, and the abandoned encode cache. Use a local `config` returned by `load_rife_model()` to initialize the retained fields.

Remove `device`, `dtype`, `modulo`, and `has_head` properties because repository-wide call analysis finds no consumer; internal code already accesses private state directly.

The ONNX solver drops its write-only `_model_version` field while retaining modulo, session I/O names, and grid caches.

## Contracts

Architecture checks reject restoration of the removed fields and properties. Tests exercise actual initialization and inference paths rather than private snapshots.

## Non-Goals

- Do not change `load_rife_model()` return values or constructor parameters.
- Do not remove active grid/session/model state.
- Do not implement Anime optimization behavior or change capability metadata.
- Do not modify RIFE checkpoint modules.
