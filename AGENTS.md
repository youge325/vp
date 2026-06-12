# 仓库指南

## 项目结构与模块组织

VP Workbench 是基于 Tauri v2 的桌面视频处理应用。`backend/app/` 放置 Python CLI、流式处理链路、算法、协议和工具模块；`backend/tests/` 是 pytest 测试。`frontend/src/` 放置 Vue 3 + TypeScript 前端、Pinia 状态、路由、组合式函数和 IPC 封装。`frontend/src-tauri/src/` 是 Rust 桌面外壳，负责 Tauri 命令、任务控制、权限和进程管理。`frontend/e2e/` 存放 WebdriverIO 桌面端测试。`docs/` 是架构与开发文档，`scripts/` 是契约检查脚本，`infra/` 是运行器和部署配置。

## 构建、测试与开发命令

命令行优先使用 `pwsh`；Python 命令使用 `python`，不要使用 `python3`。

- `cd backend; python -m pytest tests -q`：运行后端测试。
- `cd backend; python -m app benchmark --report-json ../test-results/benchmark-report.json --report-markdown ../test-results/benchmark-report.md`：生成 benchmark 回归报告。
- `cd frontend; npm install`：安装前端依赖。
- `cd frontend; npm run test`：运行 Vitest 单元测试。
- `cd frontend; npm run build`：执行 TypeScript 检查和 Vite 生产构建。
- `cd frontend; npm run tauri:dev`：启动桌面端开发模式。
- `cd frontend/src-tauri; cargo test --quiet`：运行 Rust 测试。
- `pre-commit run --all-files`：运行格式化、lint 和仓库契约检查。

## 代码风格与命名约定

Python 目标版本为 3.12，使用 Ruff：行宽 120、空格缩进、双引号。测试文件放在 `backend/tests/`，命名为 `test_*.py`。TypeScript/Vue 使用 ESM，`@` 指向 `frontend/src`，单元测试使用同目录或相近目录的 `*.spec.ts`。组件和组合式函数遵循现有命名，例如 `StageModuleView.vue`、`useWorkbenchEditor.ts`。Rust 使用 edition 2021，提交前运行 `cargo fmt`。

## 测试指南

后端测试使用 pytest，涉及重型框架加载时使用 `paddle`、`pytorch` 等 marker；避免在同一测试进程混用不兼容的 GPU 框架。前端单元测试运行在 Vitest + `jsdom`，匹配 `src/**/*.spec.ts`。桌面端 E2E 通过 `cd frontend; npm run e2e` 运行，需要已构建的 Tauri 可执行文件。修改 Rust 模型、Tauri 命令或跨语言协议时，运行 `cargo build`、`npm run build` 和 pre-commit，确保生成类型与契约一致。

## Commit 与 Pull Request 规范

近期提交使用简短祈使句主题，通常为英文句首大写，例如 `Fix benchmark model directory fallback`、`Add backend benchmark regression system`。保持每个 commit 聚焦于单一层面或单一问题。仓库所有者进行开发时，不提交 PR；本地验证通过后直接推送到 `main` 分支。非所有者或协作分支仍应提交 PR，说明影响的 backend/frontend/Rust 范围，列出已执行的验证命令，关联相关 issue；涉及 UI 的改动需提供截图或录屏。单独说明生成文件变更，尤其是 Tauri schema 和 ts-rs 生成的 TypeScript 类型。

## 安全与配置提示

不要提交本地模型权重、运行时包、日志、视频文件或 `node_modules`。本地运行配置通过环境变量覆盖，例如 `VP_PYTHON_EXECUTABLE`、`VP_FFMPEG_PATH`、`VP_FFPROBE_PATH`、`VP_RIFE_MODEL_DIR`、`VP_TENSORRT_DIR`。
