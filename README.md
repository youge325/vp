# VP Workbench

基于 Tauri 的桌面工作台，用于视频补帧、超分辨率流程编排、面向动漫的交付预设、格式转换与结果交接。

## 技术栈

- `backend/`：Python CLI 核心，当前仍是唯一的处理后端。
- `frontend/`：Vue 3 + TypeScript + Vite + Pinia + Vue Router。
- `frontend/src-tauri/`：Tauri v2 外壳，负责文件对话框、运行时/资源解析、进程管理与事件转发。

## 变更内容

- 移除了旧版 `web/` Gradio 前端。
- 移除了旧版 `desktop/` PyQt 前端。
- 将 UI 重建为 8 步暗色工作台：
  1. 概览
  2. 素材
  3. 视频补帧
  4. 超分辨率
  5. 动漫优化
  6. 格式转换
  7. 输出与执行
  8. 结果预览
- 保持以后端契约 `python -m app check|info|process` 为中心。
- 将后端 CLI 错误升级为稳定结构：`code + message + details`。
- 增加了 Tauri 任务生命周期管线：
  - invokes: `pick_input`, `pick_output`, `check_environment`, `inspect_video`, `start_task`, `cancel_task`, `open_output_location`, `open_file_or_directory`
  - events: `task-progress`, `task-log`, `task-completed`, `task-error`, `task-cancelled`

## 本地开发

### 1. 后端测试

```powershell
python -m pytest backend\tests\test_cli.py backend\tests\test_processing\test_ffmpeg_wrapper.py -q
```

### 2. 安装前端依赖

```powershell
cd frontend
npm install
```

### 3. 前端单元测试

```powershell
npm run test
```

### 4. 浏览器预览

```powershell
npm run dev
```

这对布局开发很有用，但仅限 Tauri 的命令需要在桌面外壳中运行。

### 5. Tauri 桌面开发

```powershell
cd frontend
npm run tauri:dev
```

### 6. 生产环境 Web 资源构建

```powershell
cd frontend
npm run build
```

### 7. Rust 外壳测试

```powershell
cd frontend\src-tauri
cargo test
```

## 资源布局

Tauri 外壳按以下顺序解析资源：

1. 显式环境变量覆盖，例如 `VP_FFMPEG_PATH`、`VP_FFPROBE_PATH`、`VP_RIFE_MODEL_DIR`、`VP_RUNTIME_ROOT`、`VP_PYTHON_EXECUTABLE`
2. `frontend/src-tauri/resources/` 中打包的运行时资源
3. 开发阶段相对工作区的源码布局
4. 系统 Python 兜底

在运行时，外壳会强制使用应用本地可写的临时目录和输出目录，避免打包构建尝试写入只读的内置资源目录。

## 架构图文档

- 参数传递架构图：`docs/architecture-parameter-flow.md`
- 字段级映射图：`docs/field-level-mapping.md`

## 备注

- 当前桌面外壳已经可以通过基于进程组的桥接启动、取消并监控后端任务。
- 右侧摘要面板会始终反映来源、策略、运行时、编码与输出状态。
- 即使后端算法实现仍在演进，“动漫优化”和“超分辨率”页面也已作为一等工作流界面接入。
