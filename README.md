# 视频补帧与超分软件

> 无状态 CLI 后端 · subprocess 调用 · FFmpeg 视频处理管道 · PyTorch/PaddlePaddle 双 Tensor 后端

## 项目简介

基于深度学习的视频补帧与超分辨率处理软件，支持视频补帧（RIFE v4.25）、超分辨率（Real-ESRGAN）、动漫帧优化及格式转换。采用管道-过滤器 + 工厂 + 策略架构，提供桌面端（PyQt6）和网页端（Gradio）两种前端界面。

后端为无状态命令行工具，前端通过 `subprocess` 调用，无需启动 HTTP 服务器，无需数据库。

## 系统架构

```
┌────────────────┐     ┌────────────────┐
│  PyQt6 桌面端   │     │  Gradio 网页端  │
│  (desktop/)    │     │   (web/)       │
│  CliClient     │     │  CliClient     │
└───────┬────────┘     └───────┬────────┘
        │ subprocess 调用       │
        └───────────┬──────────┘
                    ▼
         ┌──────────────────────┐
         │  CLI 后端 (backend/)  │
         │  python -m app       │
         │  ┌────────────────┐  │
         │  │ 命令解析层      │  │
         │  │  process|info   │  │
         │  │  check          │  │
         │  ├────────────────┤  │
         │  │ 处理管道层      │  │
         │  │  DecodeFilter → │  │
         │  │  FrameProcess → │  │
         │  │  EncodeFilter   │  │
         │  ├────────────────┤  │
         │  │ 算法层          │  │
         │  │  Factory +      │  │
         │  │  RIFESolver +   │  │
         │  │  TensorBackend  │  │
         │  └────────────────┘  │
         │   FFmpeg 命令行封装   │
         └──────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python CLI (argparse)，无状态，stdout JSON 行协议 |
| 数据验证 | Pydantic 2.9 + pydantic-settings |
| 视频处理 | FFmpeg (命令行封装) |
| 深度学习 | PyTorch (RIFE v4.25) / PaddlePaddle (Tensor 后端) |
| 补帧模型 | RIFE v4.25 (Real-Time Intermediate Flow Estimation) |
| 桌面端 | PyQt6 |
| 网页端 | Gradio |
| 测试 | pytest 8.3 |

## 项目结构

```
vp/
├── backend/           # CLI 后端
│   ├── app/
│   │   ├── __main__.py  # python -m app 入口
│   │   ├── cli.py       # CLI 主逻辑
│   │   ├── config.py    # 配置 (FFmpeg/处理参数/RIFE)
│   │   ├── processing/  # 管道-过滤器 (解码→处理→编码)
│   │   │   ├── decoder.py        # FFmpeg 解码
│   │   │   ├── frame_processor.py # 帧处理（逐帧/帧对双模式）
│   │   │   ├── encoder.py        # FFmpeg 编码 + 音频合并
│   │   │   ├── interpolation.py  # RIFE 补帧算法
│   │   │   └── ...
│   │   ├── algorithms/  # 算法插件 (工厂 + 策略模式)
│   │   │   ├── base.py          # IAlgorithm 接口（含帧对处理方法）
│   │   │   ├── factory.py       # AlgorithmFactory 工厂
│   │   │   ├── tensor_backend.py # PyTorch/PaddlePaddle 后端
│   │   │   └── rife/            # RIFE 模型子包
│   │   │       ├── __init__.py   # RIFESolver 统一推理接口
│   │   │       ├── ifnet_v4_25.py # RIFE v4.25 网络定义
│   │   │       ├── warplayer.py   # 光流后向变形（线程安全）
│   │   │       └── model_loader.py # 权重加载/自动下载
│   │   └── utils/       # FFmpeg 封装、文件工具
│   ├── models/         # 模型权重文件目录
│   └── tests/          # 单元测试
├── desktop/           # PyQt6 桌面端
│   ├── views/
│   │   └── main_window.py  # 主窗口 (单面板 + 状态栏)
│   ├── api_client.py  # 后端 CLI 客户端 (subprocess)
│   └── main.py        # 入口
└── web/               # Gradio 网页端
    ├── app.py         # 单页面应用
    ├── api_client.py  # 后端 CLI 客户端 (subprocess)
    └── requirements.txt
```

## 快速开始

### 环境要求

- Python 3.10+
- PyTorch（CUDA 支持推荐）
- FFmpeg（配置路径见后端 `.env` 或 `config.py`）
- （可选）NVIDIA GPU + CUDA 用于加速

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 检查环境

```bash
python -m app check
```

### 查询视频信息

```bash
python -m app info --input /path/to/video.mp4
```

### 执行视频补帧

```bash
# 2x 补帧（默认），30fps → 60fps
python -m app process --input /path/to/video.mp4 --algorithm frame_interpolation

# 4x 补帧，30fps → 120fps
python -m app process --input /path/to/video.mp4 --algorithm frame_interpolation --multi 4

# 4K 视频使用半分辨率处理 + 半精度推理
python -m app process --input /path/to/4k_video.mp4 --multi 2 --scale 0.5 --fp16
```

### 启动桌面端

```bash
cd desktop
pip install PyQt6
python main.py
```

### 启动网页端

```bash
cd web
pip install -r requirements.txt
python app.py
# 访问 http://localhost:7860
```

## 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 视频补帧 | RIFE v4.25 模型，2x/4x 倍率，支持 4K 缩放和半精度 | ✅ 已集成 |
| 超分辨率 | 2x/4x 放大，计划集成 Real-ESRGAN 等算法 | 🔲 计划中 |
| 动漫帧优化 | 重复帧检测与过渡优化 | 🔲 计划中 |
| 格式转换 | 支持多种编码器 (H.264/H.265/VP9/AV1) | ✅ 已支持 |

## RIFE 补帧原理

RIFE（Real-Time Intermediate Flow Estimation）是一种基于光流的实时视频插帧方法：

1. **Head 编码**：将输入帧 I0、I1 编码为特征图 f0、f1
2. **5 级 IFBlock 级联**：逐级细化光流估计
   - block0：首级估计，输入 (I0, I1, f0, f1, timestep)
   - block1~4：级联细化，使用 warp 后的特征和上一级光流
3. **Warp 融合**：基于最终光流和 mask 混合两帧的变形结果

CLI 参数：
- `--multi`：补帧倍率（2=2x, 4=4x），每对帧生成 (multi-1) 个中间帧
- `--model`：RIFE 模型版本（默认 4.25）
- `--scale`：处理分辨率缩放（1.0 原始，0.5 适用于 4K）
- `--fp16`：半精度推理（需 GPU 支持，速度提升约 2 倍）

## 设计模式

- **管道-过滤器 (Pipe-Filter)**：`DecodeFilter → FrameProcessFilter → EncodeFilter`
- **策略 (Strategy)**：`IAlgorithm` 抽象基类，算法可替换
- **工厂 (Factory)**：`AlgorithmFactory` 根据类型创建算法实例
- **适配器 (Adapter)**：`FFmpegWrapper` 适配 FFmpeg 命令行
- **双模式处理**：FrameProcessFilter 根据算法类型自动选择逐帧处理或帧对插值

## JSON 行协议

CLI 通过 stdout 输出 JSON 行，前端逐行解析：

```
{"type":"progress","current":1,"total":100,"percent":1.0}
{"type":"completed","output_path":"...","processed_frames":100,"time_seconds":12.3}
{"type":"error","message":"..."}
{"type":"info","fps":30.0,"frames":900,...}
{"type":"check","ffmpeg":{...},"gpu":{...},"tensor_backends":{...},"rife_model":{...}}
```

## 测试

```bash
cd backend
python -m pytest tests/ -v
```

## 配置

后端支持环境变量和 `.env` 文件，前缀 `VP_`：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `VP_FFMPEG_PATH` | D:\Lenovo\FFmpeg\bin\ffmpeg.exe | FFmpeg 路径 |
| `VP_FFPROBE_PATH` | D:\Lenovo\FFmpeg\bin\ffprobe.exe | FFprobe 路径 |
| `VP_TEMP_DIR` | backend/temp | 临时文件目录 |
| `VP_OUTPUT_DIR` | backend/output | 输出文件目录 |
| `VP_MAX_CONCURRENT_TASKS` | 1 | 最大并发任务数 |
| `VP_DEFAULT_TENSOR_BACKEND` | pytorch | 默认 Tensor 后端 |
| `VP_RIFE_MODEL_DIR` | backend/models | RIFE 模型权重目录 |
| `VP_RIFE_MODEL_VERSION` | 4.25 | RIFE 模型版本 |
| `VP_RIFE_SCALE` | 1.0 | 处理分辨率缩放 |
| `VP_RIFE_FP16` | False | 是否使用半精度推理 |
| `VP_RIFE_DEFAULT_MULTI` | 2 | 默认补帧倍率 |

## License

MIT
