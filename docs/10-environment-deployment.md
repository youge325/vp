# 环境与部署

## 运行时资源解析

桌面外壳按以下优先级解析运行时资源：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | 显式环境变量（`VP_*`） | 最高优先级，覆盖所有其他来源 |
| 2 | 打包资源目录 | `frontend/src-tauri/resources/runtime/` |
| 3 | 开发环境源码布局 | 工作区根目录下的 `backend/` |
| 4 | 系统级 PATH | 系统 PATH 中的可执行文件 |

[`frontend/src-tauri/src/runtime/mod.rs`](../frontend/src-tauri/src/runtime/mod.rs) 在 `lib.rs::setup` 中调用一次 `resolve_runtime_paths()`，结果存入 managed state，后续命令直接读取。

### 各资源查找策略

**Python 可执行文件**：
1. `VP_PYTHON_EXECUTABLE` 环境变量（绝对路径）
2. 打包目录中的 bundled Python（`resources/runtime/python/python.exe`）
3. 系统 PATH 中的 `python.exe`（Windows）或 `python3`（Linux/macOS）

Release 构建默认不再打包 Python 运行时。若系统 PATH 中已存在兼容的 Python（3.12+），无需额外配置。

**FFmpeg / FFprobe**：
1. `VP_FFMPEG_PATH` / `VP_FFPROBE_PATH` 环境变量
2. `resources/runtime/ffmpeg/bin/ffmpeg.exe`
3. 开发环境 `backend/` 下的 FFmpeg
4. 系统 PATH

**模型目录**：
1. `VP_RIFE_MODEL_DIR` 环境变量
2. `resources/runtime/models/`
3. 开发环境 `backend/models/`

**TensorRT（可选）**：
1. `VP_TENSORRT_DIR` 环境变量
2. 未设置时自动降级到 CUDA EP

桌面外壳通过 `build_env_map` 将所有解析到的路径和环境变量透传给 Python 子进程。Python 端 [`backend/app/utils/dll_paths.py`](../backend/app/utils/dll_paths.py) 在创建 ONNX session 前自动将 `<dir>/bin` 注册到 DLL 搜索路径，无需手动修改系统 PATH。

## 环境变量完整清单

| 变量名 | Rust 读取 | Python 读取 | 说明 |
|--------|----------|------------|------|
| `VP_FFMPEG_PATH` | ✅ | — | FFmpeg 可执行文件路径 |
| `VP_FFPROBE_PATH` | ✅ | — | FFprobe 可执行文件路径 |
| `VP_PYTHON_EXECUTABLE` | ✅ | — | Python 可执行文件路径 |
| `VP_RIFE_MODEL_DIR` | ✅ | ✅ | RIFE 模型目录 |
| `VP_RUNTIME_ROOT` | ✅ | — | 运行时资源根目录 |
| `VP_TENSORRT_DIR` | ✅ | ✅ | TensorRT 安装目录 |
| `VP_TASK_STALL_TIMEOUT_SECS` | ✅ | — | Watchdog 超时秒数（0 禁用） |

## 本地持久化路径

Tauri 的 `app_handle.path()` API 自动处理各平台差异：

| 数据 | Windows | Linux | macOS |
|------|---------|-------|-------|
| 环境缓存 | `%APPDATA%/com.lenovo.vp.workbench/` | `~/.config/com.lenovo.vp.workbench/` | `~/Library/Application Support/com.lenovo.vp.workbench/` |
| 文件名 | `environment-cache.json` | 同上 | 同上 |
| 预设文件 | `workbench-preset.json` | 同上 | 同上 |

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
- **默认 RIFE 模型**：`resources/runtime/models/flownet_v4.25.pkl`
- **Python 运行时（可选）**：`resources/runtime/python/python.exe`

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
      "title": "VP Workbench",
      "width": 1280,
      "height": 860,
      "minWidth": 1040,
      "minHeight": 760
    }]
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
| `build.yml` | push/PR 到 main/master/develop | Windows 自托管构建，生成便携包 zip |
| `release.yml` | push v* 标签 | 构建并发布到 GitHub Release |
| `test-backend.yml` | push/PR 修改 backend/ | PyTorch 和 Paddle 后端测试 |
| `test.yml` | push/PR 修改 backend/app/ 或 frontend/ | 前端测试 + 类型检查 + 错误码一致性检查 |

## 平台差异

| 功能 | Windows | Linux | macOS |
|------|---------|-------|-------|
| 桌面窗口 | ✅ 完整支持 | ✅ | ✅ |
| 进程暂停/恢复 | ✅ Win32 API | ❌ SIGSTOP/SIGCONT（占位） | ❌ 占位 |
| FFmpeg 打包 | ✅ | ✅ | ✅ |
| Python 打包 | ✅ 可选 | ✅ 可选 | ✅ 可选 |

当前主要开发和测试平台为 Windows。Linux/macOS 的进程暂停/恢复功能尚未实现，但其他功能完整可用。
