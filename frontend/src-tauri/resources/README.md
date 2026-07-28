# Bundled Runtime Layout

Release builds populate this directory through `scripts/prepare-windows-runtime.ps1`.

Required Windows structure:

- `resources/runtime/ffmpeg/bin/`
- `resources/runtime/models/`
- `resources/config/`

Optional (for bundled Python):

- `resources/runtime/python/` — only when distributing a self-contained Python runtime.
  Release builds no longer bundle Python by default to reduce package size.
  Users should install Python separately or set `VP_PYTHON_EXECUTABLE`.

The packaging script reads these build-time overrides when auto-detection is not enough:

- `VP_RELEASE_PYTHON_ROOT` or `VP_RELEASE_PYTHON_EXE`
- `VP_RELEASE_FFMPEG_DIR`
- `VP_RELEASE_MODEL_DIR`
- `VP_RELEASE_PYTHON_COPY_MODE` (`slim` by default, `full` for emergency fallback)
- `VP_RELEASE_PYTHON_PACKAGES` (comma/semicolon separated extra package globs for slim mode)

Self-hosted CI does not commit `.pkl` model weights to Git. `scripts/setup-ci-runtime-env.ps1`
resolves the local runner Python, FFmpeg, and weight directories for later workflow steps.
CI uses `D:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe` explicitly
instead of relying on `PATH`. Set `VP_CI_MODEL_DIR` when moving to a new runner, or keep
weights in one of the default local locations:

- `D:\Lenovo\vp\backend\models`
- `D:\actions-runner-vp\_assets\models`

At runtime the app resolves dependencies in this priority order:

1. Environment variable overrides (`VP_PYTHON_EXECUTABLE`, `VP_FFMPEG_PATH`, etc.)
2. Bundled resources under `resources/runtime/`
3. System `PATH` lookup for Python only

Release builds no longer require bundled Python. If Python is not bundled and not
explicitly configured, the app will search for `python.exe` (Windows) or `python3`
(Linux/macOS) in the system `PATH`. FFmpeg and FFprobe must come from explicit
overrides or the canonical bundled runtime in release builds.
