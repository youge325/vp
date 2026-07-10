# VP Workbench Round 24 Test-Only Bootstrap Removal Design

## Goal

Remove `app.processing.register_default_algorithms()`, which has no production caller and exists only to initialize pytest state.

## Design

Production stage workers continue to register exactly one algorithm through `stage_worker_factory` after reading the stage config. `app.processing` becomes a side-effect-free package with no algorithm imports or registry bootstrap.

The session pytest fixture registers the four concrete algorithm classes directly for tests that bypass stage-worker creation. This keeps test setup in the test layer and makes the production execution path authoritative.

`AlgorithmFactory.create()` keeps its empty-registry guard, but its error explains the actual invariant: the required algorithm must be registered before creation. CLI tests stop monkeypatching a removed bootstrap symbol. Architecture contracts reject future reintroduction in production sources.

## Verification

Run the factory tests through RED/GREEN, then algorithm, stage-worker, CLI, architecture, frontend build, and pre-commit gates. No wire or processing behavior changes.
