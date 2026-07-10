# VP Workbench Round 27 Data Rule Deduplication Design

## Goal

Remove duplicated scalar/schema rules and one unreachable vendor module without changing UI, IPC, CLI, NDJSON payloads, preset data, model selection, or inference behavior.

## Frontend

`model-metric-format.ts` and `model-runtime-estimates.ts` own identical private `finiteOrNull()` functions. Add a single pure `finiteNumberOrNull()` helper under `frontend/src/services/` and make both services depend on it. The runtime estimator also computes `parameterCount` once instead of applying the same coercion repeatedly.

The helper remains small and domain-neutral: it accepts `number | null | undefined`, returns finite numbers unchanged, and maps non-finite or absent values to `null`.

## Backend

Use Pydantic's supported `pydantic.alias_generators.to_camel` in both IPC config models and NDJSON payload models. The current private implementations are byte-for-byte equivalent for every declared model field, so this removes duplicate schema behavior while preserving aliases.

Keep `RifeModelSpec` and `MODEL_SPECS` as the RIFE metadata source of truth. Remove the derived global `MODEL_CONFIGS` copy and migrate ONNX export, ONNX runtime, and tests to typed spec attributes. `RifeModelSpec.to_dict()` stays because `load_rife_model()` still returns the existing internal config-dict shape consumed by the PyTorch solver.

Delete `vendor/ppgan/utils/logger.py`: static module and symbol analysis finds no application or test import, and PaddleGAN runtime logging uses the application's logger instead.

## Contracts

Architecture checks reject local frontend finite-number implementations, private camel alias generators, the RIFE legacy global config, and restoration of the dead vendor logger module.

## Verification Boundaries

Run frontend service tests, schema drift tests, protocol payload tests, RIFE tests, and PaddleGAN tests. PyTorch and Paddle tests remain in separate pytest processes. Finish with architecture contracts, frontend full tests/build, and pre-commit.

## Non-Goals

- Do not change `load_rife_model()` return values.
- Do not merge version-specific RIFE network files; their duplicated structures mirror checkpoint state dictionaries.
- Do not remove the supported offline ONNX export utility.
- Do not alter error-event emission or protocol payload fields.
