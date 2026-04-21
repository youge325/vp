# Bundled Runtime Layout

Put platform-specific bundled resources under this directory when preparing a release build.

Suggested structure:

- `resources/runtime/python/`
- `resources/runtime/ffmpeg/bin/`
- `resources/runtime/models/`
- `resources/config/`

At runtime the app first checks environment overrides, then bundled resources, then falls back to
workspace-relative paths or system tools.
