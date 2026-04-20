# 桌面端 — 视频补帧与超分软件

> PyQt6 桌面客户端 · 暗色主题 · Slate/Teal 色系 · subprocess 调用后端

## 简介

基于 PyQt6 的桌面客户端，通过 subprocess 调用 CLI 后端（`python -m app`），无需启动 HTTP 服务器。提供环境检查、视频信息查询、视频处理等功能。

## 目录结构

```
desktop/
├── __init__.py
├── main.py               # 应用入口
├── api_client.py         # 后端 CLI 客户端 (subprocess)
└── views/
    ├── __init__.py
    └── main_window.py    # 主窗口 (单面板 + 状态栏)
```

## 快速开始

### 1. 安装依赖

```bash
pip install PyQt6
```

### 2. 启动桌面端

```bash
python main.py
```

无需单独启动后端服务器，`CliClient` 会自动通过 subprocess 调用后端 CLI。

## 功能模块

### 主窗口 (`main_window.py`)

- 单面板布局（无标签页）
- 暗色主题 (Slate/Teal 色系，背景 `#0F172A`，主色 `#00D4AA`)
- 状态栏：显示就绪状态
- 环境检查：检查 FFmpeg/GPU/Tensor 后端可用性

## CLI 客户端 (`api_client.py`)

`CliClient` 类封装了与后端 CLI 的所有交互：

| 方法 | 说明 |
|------|------|
| `process(input_path, algorithm, ...)` | 执行视频处理管道（阻塞） |
| `process_async(input_path, ...)` | 在后台线程中执行处理 |
| `get_video_info(input_path)` | 查询视频信息 |
| `check_environment()` | 检查环境可用性 |

客户端自动检测 `backend/` 目录位置，使用当前 Python 解释器执行 `python -m app`。

## 主题样式

暗色主题，主要颜色：

| 元素 | 颜色 |
|------|------|
| 背景 | `#0F172A` (Slate 900) |
| 主色 | `#00D4AA` (Teal) |
| 悬停 | `#0EA5E9` (Sky 500) |
| 文字 | `#CBD5E1` (Slate 300) |
| 次要文字 | `#94A3B8` (Slate 400) |

## 支持的视频格式

`.mp4` `.avi` `.mkv` `.mov` `.webm` `.flv` `.wmv` `.ts` `.m2ts` `.vob`

## 依赖

```
PyQt6
```
