# 视频补帧与超分软件 — 后端 CLI

无状态命令行工具，前端通过 `subprocess` 调用，无需启动服务器。

## 快速开始

```bash
cd backend

# 检查环境
python -m app check

# 查询视频信息
python -m app info --input /path/to/video.mp4

# 执行视频处理
python -m app process --input /path/to/video.mp4 --algorithm frame_interpolation --fps 60
```

## CLI 子命令

### `process` — 执行视频处理管道

```bash
python -m app process --input VIDEO [OPTIONS]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | (必填) | 输入视频文件路径 |
| `--output` | 自动生成 | 输出文件路径 |
| `--algorithm` | `frame_interpolation` | 处理算法: `frame_interpolation`, `super_resolution`, `anime_optimization`, `format_conversion` |
| `--fps` | `60` | 目标帧率 |
| `--codec` | `libx264` | 视频编码器 |
| `--crf` | `18` | CRF 质量 (0-51) |
| `--preset` | `medium` | 编码预设 |
| `--backend` | `pytorch` | Tensor 后端: `pytorch`, `paddle` |
| `--temp-dir` | 配置默认值 | 临时文件目录 |
| `--output-dir` | 配置默认值 | 输出文件目录 |

### `info` — 查询视频信息

```bash
python -m app info --input VIDEO
```

输出 JSON：`{"type":"info","fps":30.0,"frames":900,"duration":30.0,"has_audio":true,"width":1920,"height":1080}`

### `check` — 检查环境可用性

```bash
python -m app check
```

输出 JSON：`{"type":"check","ffmpeg":{"available":true,...},"gpu":{...},"tensor_backends":{"pytorch":true,"paddle":false}}`

## JSON 行协议

CLI 通过 stdout 输出 JSON 行，前端逐行解析：

```
{"type":"progress","current":1,"total":100,"percent":1.0}
{"type":"progress","current":50,"total":100,"percent":50.0}
{"type":"completed","output_path":"...","processed_frames":100,"time_seconds":12.3}
{"type":"error","message":"..."}
```

## 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── __main__.py      # python -m app 入口
│   ├── cli.py           # CLI 主逻辑
│   ├── config.py        # 配置 (FFmpeg/处理参数)
│   ├── algorithms/      # 算法 (工厂模式)
│   ├── processing/      # 管道-过滤器 (解码→处理→编码)
│   └── utils/           # FFmpegWrapper, 文件工具
├── requirements.txt
└── README.md
```

## 配置

通过环境变量（前缀 `VP_`）或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VP_FFMPEG_PATH` | `D:\Lenovo\FFmpeg\bin\ffmpeg.exe` | FFmpeg 路径 |
| `VP_FFPROBE_PATH` | `D:\Lenovo\FFmpeg\bin\ffprobe.exe` | FFprobe 路径 |
| `VP_TEMP_DIR` | `backend/temp` | 临时文件目录 |
| `VP_OUTPUT_DIR` | `backend/output` | 输出文件目录 |
| `VP_DEFAULT_TENSOR_BACKEND` | `pytorch` | 默认 Tensor 后端 |

## 测试

```bash
cd backend
python -m pytest tests/ -v
```
