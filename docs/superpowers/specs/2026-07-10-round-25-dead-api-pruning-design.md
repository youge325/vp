# VP Workbench Round 25 Dead API Pruning Design

## Goal

Remove production API surfaces that repository-wide reference analysis proves are either test-only or unreachable, without changing UI, IPC, CLI, task events, preset payloads, or processing behavior.

## Frontend

`InvokeError` remains the internal structured error produced by the IPC client, but it is no longer exported. No runtime module imports the class or branches on its identity. Composable tests construct structural coded errors through a test-only helper instead of depending on an IPC implementation class.

The generated protocol barrel remains unchanged. Its complete wire-type namespace is intentional even when individual generated types do not currently have runtime importers.

## Backend

Delete only surfaces with direct repository evidence of no production consumer:

- `AlgorithmFactory.get_available_types()`, whose only callers are registration tests already covered by successful `create()` calls.
- `ITensorBackend.get_supported_devices()` / `get_supported_engines()` and their implementations, which have no caller and duplicate environment capability metadata ownership.
- `FFmpegWrapper` raw command builders, `convert_format()`, and `build_encode_video_args()`. Raw command construction remains owned and tested in `ffmpeg/io.py`; video argument construction remains owned by `ffmpeg/encode.py` and is reached through `build_encode_output_args()`.
- The unreferenced `encoder_segment_writer` state accessors.
- Five unreferenced PaddleGAN vendor initializers: `normal_`, `uniform_`, `xavier_uniform_`, `xavier_normal_`, and `kaiming_uniform_`.

Keep dynamically invoked algorithm hooks, RIFE cache methods, and model-specific flow helpers out of this batch until a separate runtime-focused audit can prove they are safe to remove.

## Contracts

Extend the architecture checker to reject reintroduction of the frontend test-only export and each removed backend surface. Focused architecture tests exercise the checker with synthetic source files before production code changes.

## Verification

Run focused frontend composable tests; backend factory, tensor backend, FFmpeg, encoder, and PaddleGAN tests; the architecture checker and its pytest suite; the frontend production build; and full pre-commit before committing and pushing `main`.
