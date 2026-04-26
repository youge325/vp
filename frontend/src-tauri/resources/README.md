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

Self-hosted CI does not commit `.pkl` model weights to Git. `scripts/setup-ci-runtime-env.ps1`
resolves the local runner weight directory and writes `VP_RELEASE_MODEL_DIR` and
`VP_RIFE_MODEL_DIR` for later workflow steps. Set `VP_CI_MODEL_DIR` when moving to a
new runner, or keep weights in one of the default local locations:

- `D:\Lenovo\vp\backend\models`
- `D:\actions-runner-vp\_assets\models`

At runtime the app first checks environment overrides, then bundled resources. Release builds fail
fast when required bundled assets are missing.
