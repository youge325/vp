# 环境与部署

本文档描述 VP Workbench 的运行时资源解析策略、环境变量配置、开发环境启动方式以及 Release 构建要求。

## 运行时资源解析

Rust 桌面外壳在启动时解析应用所需的全部外部资源路径。解析逻辑集中在 [`frontend/src-tauri/src/runtime.rs`](../frontend/src-tauri/src/runtime.rs) 和 [`backend/app/config.py`](../backend/app/config.py)。

### 四级解析优先级

所有资源（Python、FFmpeg、模型、TensorRT 等）遵循统一的解析优先级：

```
1. 显式环境变量覆盖（VP_*）
2. 打包资源目录（Tauri resource_dir 下的 resources/runtime/）
3. 开发环境源码布局（workspace_root/backend/、frontend/src-tauri/resources/runtime/）
4. 系统级 PATH 兜底
```

### Python 可执行文件查找

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `VP_PYTHON_EXECUTABLE` 环境变量 | 绝对路径，最高优先级 |
| 2 | `resources/runtime/python/python.exe` | Bundled Python（Release 构建） |
| 3 | `resources/runtime/bin/python.exe` | 备选 bundled 路径 |
| 4 | `resources/runtime/python.exe` | 直接放在 runtime 根目录 |
| 5 | 系统 PATH 中的 `python.exe`（Windows）或 `python3`（Linux/macOS） | 兜底 |

Release 构建不再强制打包 Python 运行时。若系统 PATH 中存在兼容的 Python 3.12+，无需额外配置即可运行。若需指定特定 Python 环境：

```powershell
$env:VP_PYTHON_EXECUTABLE = "D:\Python312\python.exe"
```

### FFmpeg / FFprobe 查找

| 优先级 | 来源 |
|--------|------|
| 1 | `VP_FFMPEG_PATH` / `VP_FFPROBE_PATH` |
| 2 | `resources/runtime/ffmpeg/bin/ffmpeg.exe` |
| 3 | `resources/runtime/ffprobe/bin/ffprobe.exe` |

Release 构建**强制要求** FFmpeg 和 FFprobe 必须存在（通过 bundled 或环境变量），否则启动时报错：

```
Bundled FFmpeg is missing. Set VP_FFMPEG_PATH or include resources/runtime/ffmpeg/bin/ffmpeg.exe.
```

### 模型目录查找

| 优先级 | 来源 |
|--------|------|
| 1 | `VP_RIFE_MODEL_DIR` |
| 2 | `resources/runtime/models/` |
| 3 | `resources/models/` |
| 4 | `resources/backend/models/` |
| 5 | `backend/models/`（开发源码布局） |

Release 构建强制要求默认模型 `flownet_v4.25.pkl` 必须存在：

```
Bundled RIFE model is missing. Set VP_RIFE_MODEL_DIR or include resources/runtime/models/flownet_v4.25.pkl.
```

### TensorRT 查找

| 优先级 | 来源 |
|--------|------|
| 1 | `VP_TENSORRT_DIR` |
| 2 | `resources/runtime/tensorrt/` |
| 3 | `resources/tensorrt/` |

未设置时引擎自动降级到 CUDA EP，不会报错。设置后，Python 后端会在创建 ONNX session 前自动将 `<dir>/bin` 注册到 Windows DLL 搜索路径：

```python
# backend/app/utils/dll_paths.py
register_native_dll_paths(tensorrt_dir)
```

## 环境变量完整清单

| 环境变量 | Rust 层读取 | Python 层读取 | 说明 |
|----------|------------|--------------|------|
| `VP_APP_ROOT` | ❌ | ✅ | 应用根目录 |
| `VP_RUNTIME_ROOT` | ✅ | ✅ | 运行时资源根目录 |
| `VP_PYTHON_EXECUTABLE` | ✅ | ✅ | Python 可执行文件路径 |
| `VP_FFMPEG_PATH` | ✅ | ✅ | FFmpeg 可执行文件路径 |
| `VP_FFPROBE_PATH` | ✅ | ✅ | FFprobe 可执行文件路径 |
| `VP_RIFE_MODEL_DIR` | ✅ | ✅ | RIFE 模型权重目录 |
| `VP_RIFE_MODEL_VERSION` | ❌ | ✅ | 默认模型版本（默认 "4.25"） |
| `VP_OUTPUT_DIR` | ✅ | ✅ | 输出目录 |
| `VP_LOG_DIR` | ✅ | ✅ | 日志目录 |
| `VP_TENSORRT_DIR` | ✅ | ✅ | TensorRT 安装根目录 |
| `VP_BACKEND_DIR` | ✅ | ❌ | Python 代码目录（Rust 专用） |

Rust 层通过 `build_env_map()` 将解析到的路径注入到 Python 子进程的环境变量中。Python 层通过 `pydantic-settings`（`env_prefix="VP_"`）从环境变量读取配置。

## 本地持久化路径

Rust 层使用 Tauri 的 `app_local_data_dir()` 作为持久化根目录：

- **Windows**：`%LOCALAPPDATA%\com.vp-workbench.app\`
- **macOS**：`~/Library/Application Support/com.vp-workbench.app/`
- **Linux**：`~/.local/share/com.vp-workbench.app/`

在此目录下创建两个文件：

| 文件 | 用途 | 版本控制 |
|------|------|---------|
| `environment-cache.json` | 环境检查结果缓存 | `schema_version: 1` |
| `workbench-preset.json` | 用户工作台预设 | `schema_version: 1` |

## 开发环境启动

### 后端测试

```powershell
cd backend
python -m pytest tests -q
```

### 前端开发服务器

```powershell
cd frontend
npm install
npm run dev
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

### Tauri 桌面开发（完整应用）

```powershell
cd frontend
npm run tauri:dev
```

这会同时启动 Vite 前端开发服务器和 Tauri 桌面窗口。

### Rust 测试

```powershell
cd frontend\src-tauri
cargo test --quiet
```

## TensorRT 加速配置（可选）

ONNX 引擎默认走 CUDA EP。启用 TensorRT EP 需要：

1. 安装 `onnxruntime-gpu` 1.20+（自带 TRT provider DLL）
2. 下载并解压 NVIDIA TensorRT 10.x（与 CUDA 版本匹配，如 CUDA 13 对应 TRT 10.14）
3. 设置环境变量：

```powershell
$env:VP_TENSORRT_DIR = "D:\TensorRT-10.14.1.48"
```

无需手动修改系统 PATH，桌面外壳会自动将 `<dir>/bin` 注册到 DLL 搜索路径并透传给 Python 子进程。

## Release 构建要求

### 必须打包的资源

Release 构建（`npm run tauri:build`）要求以下资源必须存在于打包目录中：

1. **FFmpeg**：`resources/runtime/ffmpeg/bin/ffmpeg.exe` 和 `ffprobe.exe`
2. **默认 RIFE 模型**：`resources/runtime/models/flownet_v4.25.pkl`
3. **Python 运行时**（可选）：`resources/runtime/python/python.exe`。若省略，应用会尝试从系统 PATH 查找 Python 3.12+

### 开发 vs Release 差异

| 行为 | Debug（开发） | Release |
|------|-------------|---------|
| FFmpeg 缺失 | 允许，回退到系统 PATH | **报错退出** |
| 模型缺失 | 允许，回退到开发源码 `backend/models/` | **报错退出** |
| Python 查找 | 优先 bundled，回退系统 PATH | 优先 bundled，回退系统 PATH |
| 资源解析 | 包含 `workspace_root/backend/` 候选 | 不包含开发路径候选 |

### 构建产物

```
frontend/src-tauri/target/release/
├── vp-workbench.exe           # 主可执行文件
└── ...                        # 资源文件、DLL 依赖
```

Tauri 构建会自动将 `frontend/src-tauri/resources/` 下的文件打包到应用资源目录中。

## 平台差异

### Windows

- 进程暂停/恢复：完整支持（Win32 SuspendThread/ResumeThread）
- DLL 路径注册：自动将 TensorRT `bin/` 目录加入 DLL 搜索路径
- 进程组管理：通过 `command-group` crate 支持

### Linux / macOS

- 进程暂停/恢复：**未实现**，调用 `pause_task`/`resume_task` 返回错误提示
- 其他功能（任务启动、取消、NDJSON 协议、环境检查等）完全正常工作
- 路径查找使用 `python3` 而非 `python.exe`
