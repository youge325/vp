# VP Workbench Round 28 NDJSON Error Emission Design

## Goal

Remove redundant NDJSON error-envelope construction and an unused singleton lifecycle without changing error codes, stdout wire shape, CLI behavior, or bootstrap resilience.

## Runtime Boundary

`app.__main__` has two distinct environments:

- Before the application imports successfully, it must emit a minimal JSON error without importing protocol/Pydantic code.
- After `app.cli` and `app.protocol` load, normal `ProcessError` and unexpected-exception handling can use the typed `ndjson.error()` path.

Keep one local fallback helper for the first environment. Route both normal exception branches through `ndjson.error()`, which already constructs and validates `TaskErrorPayload`. This removes repeated hand-written `{type, code, message, details}` dictionaries while preserving the exact envelope.

## Emitter Lifecycle

The repository constructs the emitter exactly once as module-level `ndjson`. Rename the concrete class to `_NdjsonEmitter` and remove `_instance`/`__new__`; singleton state adds no behavior and broadens the protocol surface unnecessarily.

`NdjsonEventType` remains named and complete because the cross-language drift checker parses it as the Python event-name source of truth.

## Tests And Contracts

Unit tests inject failures through `app.cli.main` and verify that normal `ProcessError` and unexpected exceptions call `ndjson.error()` with normalized codes and unchanged details. Existing payload and subprocess integration tests continue verifying serialized envelopes.

Architecture contracts reject public/singleton emitter machinery and normal error branches that revert to hand-built envelope dictionaries.

## Non-Goals

- Do not change `TaskErrorPayload`, `TaskErrorCode`, or `NdjsonEventType`.
- Do not make bootstrap error emission depend on application imports.
- Do not change stderr, exit codes, traceback capture, or Tauri parsing.
