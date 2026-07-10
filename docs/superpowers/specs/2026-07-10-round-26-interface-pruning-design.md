# VP Workbench Round 26 Interface Pruning Design

## Goal

Remove one confirmed frontend rule duplication and narrow backend interfaces to methods used by production, without changing UI, IPC, CLI, task events, preset payloads, or processing behavior.

## Frontend

`enhance-options.ts` and `io-options.ts` each expose a one-line `Number(...)` converter. Move the single generic `toNumberValue(value: unknown)` rule to `preset/options.ts`, which already owns shared form-option coercion. Enhance and encode bindings import that owner directly; the specialized option modules retain only domain-specific option construction and casts.

Architecture contracts reject reintroduced numeric conversion helpers in either specialized module.

## Backend

Narrow `IAlgorithm` to the production strategy surface. Remove `process_frame_batch()`, `validate()`, and `get_description()` from the base class and concrete algorithms because repository-wide analysis finds no production caller, including dynamic string-based dispatch. Existing production hooks such as `process_frame`, `process_frame_pair`, `process_frame_sequence`, `needs_frame_pairs`, and `needs_frame_sequence` remain unchanged.

Also delete independently proven zero-reference methods:

- `interpolate_multi()` and `clear_cache()` from both RIFE solver implementations.
- `ModifiedSPyNet.compute_flow_list()` from the PaddleGAN vendor subset.
- `PipelineMetrics.timed()` and `record_stage_duration()`, plus their unreachable mutable duration state.

`PipelineMetrics.snapshot()` continues emitting `stageDurationsSeconds: {}` so NDJSON metrics and benchmark report shapes remain compatible.

## Tests And Contracts

Tests stop asserting APIs that production does not use. Frame, pair, sequence, queue, transfer, and snapshot behavior remain covered. Architecture contracts reject the removed interfaces and ensure the numeric conversion rule has one owner.

PyTorch and Paddle tests run in separate pytest processes, as required by the repository's framework-isolation rule.

## Non-Goals

- Do not remove dynamically dispatched algorithm hooks.
- Do not alter generated protocol barrels or metrics payload keys.
- Do not change model execution, frame counts, tensor conversion, or stage planning.
