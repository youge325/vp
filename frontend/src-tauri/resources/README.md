# Bundled Runtime Layout

Release builds populate this directory through `scripts/prepare-windows-runtime.ps1`.

Required Windows structure:

- `resources/runtime/python/`
- `resources/runtime/ffmpeg/bin/`
- `resources/runtime/models/`
- `resources/config/`

The packaging script reads these build-time overrides when auto-detection is not enough:

- `VP_RELEASE_PYTHON_ROOT` or `VP_RELEASE_PYTHON_EXE`
- `VP_RELEASE_FFMPEG_DIR`
- `VP_RELEASE_MODEL_DIR`

At runtime the app first checks environment overrides, then bundled resources. Release builds fail
fast when required bundled assets are missing.
