# VP Workbench

Tauri desktop workbench for video interpolation, super-resolution orchestration, anime-oriented delivery presets, format conversion, and result handoff.

## Stack

- `backend/`: Python CLI core, still the only processing backend.
- `frontend/`: Vue 3 + TypeScript + Vite + Pinia + Vue Router.
- `frontend/src-tauri/`: Tauri v2 shell for file dialogs, runtime/resource resolution, process management, and event forwarding.

## What Changed

- Removed the legacy `web/` Gradio frontend.
- Removed the legacy `desktop/` PyQt frontend.
- Rebuilt the UI as an 8-step dark workbench:
  1. 概览
  2. 素材
  3. 视频补帧
  4. 超分辨率
  5. 动漫优化
  6. 格式转换
  7. 输出与执行
  8. 结果预览
- Kept the backend contract centered on `python -m app check|info|process`.
- Upgraded backend CLI errors to stable `code + message + details`.
- Added Tauri task lifecycle plumbing:
  - invokes: `pick_input`, `pick_output`, `check_environment`, `inspect_video`, `start_task`, `cancel_task`, `open_output_location`, `open_file_or_directory`
  - events: `task-progress`, `task-log`, `task-completed`, `task-error`, `task-cancelled`

## Local Development

### 1. Backend tests

```powershell
python -m pytest backend\tests\test_cli.py backend\tests\test_processing\test_ffmpeg_wrapper.py -q
```

### 2. Frontend install

```powershell
cd frontend
npm install
```

### 3. Frontend unit tests

```powershell
npm run test
```

### 4. Browser preview

```powershell
npm run dev
```

This is useful for layout work, but Tauri-only commands require the desktop shell.

### 5. Tauri desktop dev

```powershell
cd frontend
npm run tauri:dev
```

### 6. Production web assets

```powershell
cd frontend
npm run build
```

### 7. Rust shell tests

```powershell
cd frontend\src-tauri
cargo test
```

## Resource Layout

The Tauri shell resolves resources in this order:

1. Explicit environment overrides such as `VP_FFMPEG_PATH`, `VP_FFPROBE_PATH`, `VP_RIFE_MODEL_DIR`, `VP_RUNTIME_ROOT`, `VP_PYTHON_EXECUTABLE`
2. Bundled runtime resources inside `frontend/src-tauri/resources/`
3. Workspace-relative source layout during development
4. System Python fallback

At runtime, the shell forces writable app-local temp and output directories so packaged builds do not try to write into the bundled resources directory.

## Notes

- The current desktop shell already starts, cancels, and monitors backend work through a process-group-based bridge.
- The right summary panel always reflects source, strategy, runtime, encode, and output state.
- The “动漫优化” and “超分辨率” pages are wired as first-class workflow surfaces even when the backend algorithm implementation is still evolving.
