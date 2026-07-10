# VP Workbench Round 23 Dead Surface Pruning Design

## Goal

Delete source surfaces that current repository evidence proves are not runtime APIs: frontend compile-only contract exports, an empty PaddleGAN disabled-model registry, and unused Python package re-exports.

## Frontend

`types/protocol/_contract_check.ts` remains included by `tsconfig.app.json`, so all `satisfies` checks still run during `vue-tsc`. The six constants become module-local and are explicitly consumed with `void` expressions to satisfy `noUnusedLocals`. No runtime module imports this file, and it exposes no public symbols.

## Backend

All PaddleGAN VSR specs are enabled. Remove `DISABLED_PADDLEGAN_VSR_MODELS`, the unreachable validation branch, and disabled-set handling from the architecture contract. The contract continues to require exact parity between enabled backend specs and algorithm metadata.

`app.benchmark.__init__` and `app.algorithms.paddle.paddlegan_vsr.__init__` have no import consumers for their re-exported symbols. Remove those imports and `__all__` declarations, leaving side-effect-free package documentation. Real callers already import the owning submodules directly.

## Boundaries

- No UI, IPC, CLI, task event, preset, stage-worker, or processing behavior changes.
- No dependency additions and no module relocation.
- Architecture checks reject reintroduced compile-only exports, disabled registries, validation branches, and dead package facades.

## Verification

Use architecture tests as the RED/GREEN harness, then run PaddleGAN planning/spec tests, benchmark tests, `npm run build`, the standalone architecture checker, and full pre-commit.
