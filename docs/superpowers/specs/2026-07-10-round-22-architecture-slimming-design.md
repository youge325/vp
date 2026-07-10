# VP Workbench Round 22 Architecture Slimming Design

## Goal

Reduce redundant frontend workflow forwarding and separate backend resume-manifest persistence from resume lifecycle decisions without changing UI, IPC, task events, preset payloads, or processing behavior.

## Frontend

`enhance-workflow.ts` remains the mutation-facing module consumed by form bindings. Its four backend/algorithm selection functions are currently one-to-one forwarding wrappers around `enhance-workflow-selection.ts`. Replace those function bodies with named export aliases so existing imports and function signatures remain compatible while the duplicate call layer disappears.

Enabled-state and scale/frame mutation functions remain in `enhance-workflow.ts` because they add assignment behavior rather than only forwarding.

## Backend

Add `app.planning.manifest_store` as the single owner of manifest JSON serialization, version validation, UTC timestamp creation, and atomic temporary-file replacement. `SegmentManifest` remains the public facade and continues to own resume decisions, chunk filesystem state, cleanup, and path conventions.

`SegmentManifest.MANIFEST_VERSION`, `prepare()`, `inspect()`, and all public planning exports remain compatible. The existing atomic-write test moves its monkeypatch to the persistence module, and focused store tests cover invalid JSON and version mismatch.

## Boundaries

- No cross-process payload or command changes.
- No new dependency.
- No change to resume conflict or cleanup semantics.
- Architecture contracts reject reintroduced frontend forwarding bodies and manifest JSON persistence inside `manifest.py`.

## Verification

Run targeted frontend workflow tests, backend manifest/store tests, architecture contracts, the frontend production build, and the full pre-commit suite before committing and pushing `main`.
