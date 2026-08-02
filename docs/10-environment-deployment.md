# 环境与部署

## 运行时资源解析

桌面外壳按以下优先级解析运行时资源：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | 显式环境变量（`VP_*`） | 最高优先级，覆盖所有其他来源 |
| 2 | 打包资源目录 | `frontend/src-tauri/resources/runtime/` |
| 3 | 开发环境源码布局 | 工作区根目录下的 `backend/` |
| 4 | 系统级 PATH | 仅 Python 等允许系统安装的可执行文件 |

[`frontend/src-tauri/src/runtime/mod.rs`](../frontend/src-tauri/src/runtime/mod.rs) 在 `lib.rs::setup` 中调用一次 `resolve_runtime_paths()`，结果存入 managed state，后续命令直接读取。

### 各资源查找策略

**Python 可执行文件**：
1. `VP_PYTHON_EXECUTABLE` 环境变量（绝对路径）
2. 打包目录中的 bundled Python（`resources/runtime/python/python.exe`）
3. 系统 PATH 中的 `python.exe`（Windows）或 `python3`（Linux/macOS）

Release 构建默认不打包 Python 运行时。若系统 PATH 中已存在兼容的 Python（3.12+），无需额外配置。

**FFmpeg / FFprobe**：
1. `VP_FFMPEG_PATH` / `VP_FFPROBE_PATH` 环境变量
2. `$RUNTIME_ROOT/ffmpeg/bin/ffmpeg[.exe]` 与 `$RUNTIME_ROOT/ffmpeg/bin/ffprobe[.exe]`

Rust 通过一次 `resolve_ffmpeg_tools()` 调用解析这对工具。bundle 只使用上述 canonical runtime
布局，不直接从 Tauri resource 根查找二进制。开发模式未解析到显式路径时，Python FFmpeg
wrapper 仍可回退系统 PATH；release bundle 缺少工具时拒绝启动。

**模型目录**（变量名为兼容现有 RIFE 配置，实际是统一模型根）：
1. `VP_RIFE_MODEL_DIR` 环境变量
2. `resources/runtime/models/`
3. 开发环境 `backend/models/`

**TensorRT（可选）**：
1. `VP_TENSORRT_DIR` 环境变量
2. `$RUNTIME_ROOT/tensorrt/`
3. 未解析到目录时自动降级到 CUDA EP

桌面外壳在 composition root 只解析一次 `ResolvedRuntimePaths`，后续 `build_env_map` 只投影这份
类型化结果，不重复读取第二份环境状态。TensorRT 目录进入环境缓存 fingerprint。Python 端
[`backend/app/utils/dll_paths.py`](../backend/app/utils/dll_paths.py) 在创建 ONNX session 前自动将
`<dir>/bin` 注册到 DLL 搜索路径，无需手动修改系统 PATH。

## 应用运行时环境变量

| 变量名 | Rust 读取 | Python 读取 | 说明 |
|--------|----------|------------|------|
| `VP_APP_DATA_DIR` | ✅ | — | 显式覆盖应用数据目录（主要用于 CI/E2E） |
| `VP_BACKEND_DIR` | ✅ | — | Python backend 根目录 |
| `VP_FFMPEG_PATH` | ✅ | ✅ | FFmpeg 可执行文件路径 |
| `VP_FFPROBE_PATH` | ✅ | ✅ | FFprobe 可执行文件路径 |
| `VP_LOG_DIR` | ✅ | ✅ | 日志目录 |
| `VP_PYTHON_EXECUTABLE` | ✅ | ✅ | Python 可执行文件路径 |
| `VP_RIFE_MODEL_DIR` | ✅ | ✅ | RIFE 模型目录 |
| `VP_RIFE_MODEL_VERSION` | ✅ | ✅ | 默认 RIFE checkpoint 版本 |
| `VP_RUNTIME_ROOT` | ✅ | ✅ | canonical 运行时资源根目录 |
| `VP_TENSORRT_DIR` | ✅ | ✅ | TensorRT 安装目录 |
| `VP_TASK_STALL_TIMEOUT_SECS` | ✅ | — | Watchdog 超时秒数（0 禁用） |

Python 层还接受以下有明确作用域的覆盖项；通用配置由 `_Settings` 读取，OpenCV/PaddleGAN
专用项由对应 runtime adapter 读取：

| 变量名 | 说明 |
|--------|------|
| `VP_DEBUG` | Python 日志级别开关 |
| `VP_APP_ROOT` | Python 资源解析根目录 |
| `VP_LOG_FILE_MAX_BYTES` | 单个轮转日志文件大小上限 |
| `VP_LOG_FILE_BACKUP_COUNT` | 轮转日志备份数量 |
| `VP_LOG_STARTUP_FILE_KEEP_COUNT` | 启动日志文件保留数量 |
| `VP_RIFE_SCALE` | CLI 未显式传值时的 RIFE scale |
| `VP_RIFE_FP16` | CLI 未显式传值时的 RIFE FP16 开关 |
| `VP_RIFE_DEFAULT_MULTI` | CLI 未显式传值时的插帧倍率 |
| `VP_OPENCV_BIN_DIR` / `VP_OPENCV_DIR` | Windows OpenCV DLL 搜索目录或安装根 |
| `VP_PADDLEGAN_TRT_CACHE_DIR` | PaddleGAN TensorRT engine 缓存目录 |
| `VP_PADDLEGAN_VSR_TRACE_PATH` | PaddleGAN VSR 诊断 trace 输出路径 |

## 本地持久化路径

Tauri 的 `app_handle.path()` API 自动处理各平台差异：

| 数据 | Windows | Linux | macOS |
|------|---------|-------|-------|
| 应用数据目录 | `%LOCALAPPDATA%/com.lenovo.vp.workbench/` | Tauri `app_local_data_dir` | Tauri `app_local_data_dir` |
| 文件名 | `environment-cache.json` | 同上 | 同上 |
| 预设文件 | `workbench-preset.json` | 同上 | 同上 |

环境缓存 schema 为 15，预设 schema 为 2。损坏或其他版本文件会改名为
`*.incompatible-<reason>-*.bak` 后重建，不做迁移或回退读取。release 无法解析应用数据目录时
直接启动失败；不会退到 `%TEMP%` 或安装目录伪装持久化成功。

## 开发环境启动

### 后端测试

```powershell
cd backend
python -m pytest tests -q
```

### 前端依赖安装

```powershell
cd frontend
npm install
```

### 前端测试

```powershell
cd frontend
npm run test
```

### 前端构建

```powershell
cd frontend
npm run build
```

### Tauri 桌面开发

```powershell
cd frontend
npm run tauri:dev
```

### Tauri Rust 测试

```powershell
cd frontend\src-tauri
cargo test --quiet
```

## TensorRT 加速配置

ONNX 引擎默认走 CUDA EP。启用 TensorRT EP：

1. 安装 `onnxruntime-gpu` 1.20+（自带 TRT provider DLL）
2. 下载并解压 NVIDIA TensorRT 10.x（与 CUDA 版本匹配）
3. 设置环境变量：`$env:VP_TENSORRT_DIR = "D:\TensorRT-10.14.1.48"`

未设置时引擎自动降级到 CUDA EP。

## Release 构建要求

### 必须打包的资源

- **FFmpeg**：`resources/runtime/ffmpeg/bin/ffmpeg.exe` 和 `ffprobe.exe`
- **默认 RIFE 模型**：文件名由 `contracts/application-defaults.json` 的模型版本派生，PyTorch 与
  ONNX 路径由 `scripts/runtime-tools.ps1` 统一构造并验证为非空文件
- **Real-RawVSR BasicVSR**：三份 SafeTensors 位于
  `models/super_resolution/pytorch/real-rawvsr-basicvsr/x{2,3,4}/model.safetensors`；尺寸、SHA-256、
  Google Drive 来源与运行时路径只记录在 `contracts/model-assets.json`。发布准备必须显式传入
  `--accept-noncommercial CC-BY-NC-SA-4.0-NONCOMMERCIAL`，同时打包许可与 NOTICE；应用运行时不联网下载
- **Python 运行时（可选）**：`resources/runtime/python/python.exe`

Windows portable 文件名带 `-noncommercial`。发布脚本要求系统/捆绑 Python 可导入 CUDA PyTorch 与
SafeTensors，要求三份模型和两个许可文件完整，并拒绝 `.pth/.pt/.ckpt/.pickle`。受限模型与移植代码
采用 CC BY-NC-SA 4.0，仅限非商业研究和个人使用；VP 自有代码继续采用 MIT。

### Dev vs Release 差异

| 行为 | Debug | Release |
|------|-------|---------|
| Python 打包 | 不打包，使用系统 PATH | 可选打包 |
| 运行时资源检查 | 宽松（开发路径兜底） | 严格（`require_release_bundle_artifacts`） |
| 日志级别 | debug | info / warn |
| 窗口大小 | 可调整 | 固定或最小尺寸限制 |

### Tauri 配置

[`frontend/src-tauri/tauri.conf.json`](../frontend/src-tauri/tauri.conf.json)：

```json
{
  "productName": "VP Workbench",
  "version": "0.1.0",
  "identifier": "com.lenovo.vp.workbench",
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [{
      "label": "main",
      "title": "VP Workbench",
      "width": 1280,
      "height": 860,
      "minWidth": 1040,
      "minHeight": 760
    }],
    "security": {
      "capabilities": ["default"],
      "csp": "default-src 'self' customprotocol: asset:; connect-src ipc: http://ipc.localhost; img-src 'self' asset: http://asset.localhost blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'"
    },
    "withGlobalTauri": false
  },
  "bundle": {
    "active": false,
    "resources": [
      "../../backend/app",
      "../../backend/requirements.txt",
      "./resources"
    ]
  }
}
```

## GitHub Actions 工作流

| 工作流 | 触发条件 | 职责 |
|--------|----------|------|
| `e2e.yml` | push/PR 修改 backend/app、contracts、frontend 或 scripts | Windows CLI smoke + 完整原生 WebView E2E |
| `e2e-arc.yml` | 手工 `workflow_dispatch` | Linux ARC CLI smoke + 完整原生 WebView E2E |
| `release.yml` | push v* 标签 | 构建并发布到 GitHub Release |
| `test-backend.yml` | push/PR 修改 backend、contracts 或 scripts | 以独立进程运行 PyTorch 与 Paddle 后端测试 |
| `test.yml` | push/PR 修改代码、契约、脚本或当前文档 | 契约 freshness、Rust test/clippy、前端测试/构建/静态门禁、Vulture 与全仓架构检查 |

对应的 `test-arc.yml`、`test-backend-arc.yml`、`release-arc.yml`、`benchmark-arc.yml` 和
`arc-linux-smoke.yml` 覆盖 Linux ARC、发布与性能回归路径。

E2E release 构建启用 Istanbul 插桩。当前 spec 按领域分组，在最多 10 个串行 Tauri WebView
session 内运行；每个 session 只在结束时把 renderer 内序列化的 coverage JSON 写到
`frontend/.nyc_output/`。WDIO `onPrepare` 会先清空残留 coverage，并在生成 `nyc` 报告前校验
JSON 数量为 1 至 10，避免残留文件掩盖覆盖率采集失败。`app/security.spec.ts` 校验 CSP 与本地
capability。

Windows 与 Linux 的 UI E2E job 都只构建一次插桩应用，随后让全部领域分组共享该构建。测试媒体由
`frontend/scripts/generate-e2e-fixture.mjs` 统一生成，规格为 `320x180`、`10fps`、`0.5s` 且带
音频。EdgeDriver 和两个 Rust launcher 使用 `VP_E2E_CACHE_DIR` 的持久缓存。WebDriver launcher
只在其子进程环境中移除代理变量，父 shell 和其他 `VP_*` 运行配置保持不变。

## 平台差异

| 功能 | Windows | Linux | macOS |
|------|---------|-------|-------|
| 桌面窗口 | ✅ 完整支持 | ✅ | ✅ |
| 进程暂停/恢复 | ✅ 稳定进程/线程句柄 | ✅ pidfd 集合 + SIGSTOP/SIGCONT | ❌ 明确返回 Unsupported |
| FFmpeg 打包 | ✅ | ✅ | ✅ |
| Python 打包 | ✅ 可选 | ✅ 可选 | ✅ 可选 |

当前主要开发和测试平台为 Windows。Linux 为任务树每个成员保留 pidfd 并验证启动身份后发送
`SIGSTOP/SIGCONT`；macOS 因缺少等价的稳定信号句柄而 fail closed，不按旧 PID/PGID 控制。
三个平台都保留 cancel 与 supervisor kill-and-reap；平台 CI 负责验证各自系统调用和打包路径。

## 桌面安全配置

[`frontend/src-tauri/capabilities/default.json`](../frontend/src-tauri/capabilities/default.json) 设置
`local: true` 且只匹配 `windows: ["main"]`，没有 remote origin。CSP 只允许自身脚本、Tauri IPC
连接、本地 asset/font、blob/data 图片和现有内联样式所需来源；禁止任意外网连接、`object`、
`frame` 和 `unsafe-eval`。Rust 配置测试与原生 WebView E2E 会共同阻止权限/CSP 回退。
