# 网页端 — 视频补帧与超分软件

> Gradio Web 前端 · Teal/Cyan/Slate 主题 · 全 Python 技术栈 · subprocess 调用后端

## 简介

基于 Gradio 的 Web 前端，通过 subprocess 调用 CLI 后端（`python -m app`），无需启动 HTTP 服务器，无需 Node.js，全部 Python 技术栈。

## 目录结构

```
web/
├── __init__.py
├── app.py            # Gradio 应用 (单页面)
├── api_client.py     # 后端 CLI 客户端 (subprocess)
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动网页端

```bash
python app.py
```

启动后访问：http://localhost:7860

无需单独启动后端服务器，`CliClient` 会自动通过 subprocess 调用后端 CLI。

## 功能模块

### 环境检查

| 功能 | 说明 |
|------|------|
| 检查环境 | 查看 FFmpeg/GPU/PyTorch/PaddlePaddle 可用性 |

### 视频信息

| 功能 | 说明 |
|------|------|
| 上传视频 | 支持 .mp4/.avi/.mkv/.mov/.flv/.webm/.wmv |
| 获取信息 | FPS、帧数、时长、分辨率、音频 |

### 提交处理任务

| 功能 | 说明 |
|------|------|
| 处理类型 | 视频补帧、超分辨率、动漫帧优化、格式转换 |
| 参数配置 | 目标帧率 (24-120fps)、Tensor 后端 (PyTorch/PaddlePaddle) |
| 编码选项 | 编码器 (libx264/libx265/libvpx-vp9/libaom-av1/copy) |
| 质量控制 | CRF (0-51, 越小质量越高)、编码预设 (ultrafast~veryslow) |

## CLI 客户端 (`api_client.py`)

`CliClient` 类封装了与后端 CLI 的所有交互：

| 方法 | 说明 |
|------|------|
| `process(input_path, algorithm, ...)` | 执行视频处理管道（阻塞） |
| `process_async(input_path, ...)` | 在后台线程中执行处理 |
| `get_video_info(input_path)` | 查询视频信息 |
| `check_environment()` | 检查环境可用性 |

客户端自动检测 `backend/` 目录位置，使用当前 Python 解释器执行 `python -m app`。

## 主题配置

使用 Gradio Soft 主题：

| 参数 | 值 |
|------|------|
| primary_hue | teal |
| secondary_hue | cyan |
| neutral_hue | slate |

自定义 CSS：
- 隐藏 Gradio 默认 footer

## 配置

- 服务地址：`127.0.0.1:7860`

## 依赖

```
gradio>=4.0.0
```
