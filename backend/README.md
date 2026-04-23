# Backend CLI

后端现在只保留当前正式处理链路：

- `check`：检查 FFmpeg、GPU、模型与运行时能力
- `info`：读取输入视频元数据
- `process`：走流式处理链或直接转码

不再支持旧的临时帧落盘流程，也不再提供旧版 temp 目录参数或对应环境变量。

## 快速开始

```bash
cd backend

python -m app check
python -m app info --input /path/to/video.mp4
python -m app process --input /path/to/video.mp4
```

## `process` 命令

`process` 支持两种输入方式：

1. 使用少量基础 CLI 参数生成默认配置
2. 通过 JSON 参数完整传入嵌套配置

当前桌面工作台走的是第 2 种方式。

```bash
python -m app process \
  --input /path/to/video.mp4 \
  --decode-config-json '{"mode":"hardware","hwaccel":"cuda","decoder":"hevc_cuvid","options":{}}' \
  --workflow-config-json '{"fpsMode":"target","processOrder":"frame_interpolation_then_super_resolution","interpolation":{"enabled":true,"targetFps":60,"multi":2,"model":"4.25","scale":1,"fp16":false,"tensorBackend":"pytorch"},"superResolution":{"enabled":false,"scaleFactor":2,"algorithm":"placeholder"},"anime":{"enabled":false,"profile":"clean-lines","denoise":10,"edgeBoost":15}}' \
  --encode-config-json '{"codec":"hevc_nvenc","family":"nvidia","container":"mp4","keepAudio":true,"rateControl":{"mode":"cq","value":23},"options":{"preset":"p4"}}' \
  --output-config-json '{"outputDir":"/path/to/output","openOnComplete":false,"segmentFrames":1000}'
```

### 保留的参数

| 参数 | 说明 |
| --- | --- |
| `--input` | 输入视频路径 |
| `--output` | 可选，直接指定最终输出文件路径 |
| `--output-dir` | 默认输出目录覆盖 |
| `--decode-config-json` | 解码配置 JSON |
| `--workflow-config-json` | 工作流配置 JSON |
| `--encode-config-json` | 编码配置 JSON |
| `--output-config-json` | 输出配置 JSON，包含 `segmentFrames` |

### 当前处理模型

- 有处理步骤时：解码、算法处理、编码全部走内存流式链路
- 纯 `format_conversion` 时：直接调用 FFmpeg 转码，不经过拆帧
- 开启补帧时：按 `outputConfig.segmentFrames` 分段输出中间视频，默认每 `1000` 帧一段
- 所有分段完成后：自动拼接视频并回封音频

## 输出事件

CLI 通过 stdout 逐行输出 JSON，桌面端按行消费：

```json
{"type":"progress","current":120,"total":480,"percent":25.0,"stage":"Frame Interpolation","stage_index":1,"stage_total":1}
{"type":"completed","output_path":"D:/output/demo_processed.mp4","processed_frames":960,"time_seconds":42.7}
```

失败时会输出：

```json
{"type":"error","code":"process_failed","message":"...","details":{}}
```

## 环境变量

支持通过 `VP_` 前缀环境变量覆盖运行时路径：

| 变量 | 说明 |
| --- | --- |
| `VP_APP_ROOT` | 应用根目录 |
| `VP_RUNTIME_ROOT` | bundled runtime 根目录 |
| `VP_PYTHON_EXECUTABLE` | Python 可执行文件 |
| `VP_FFMPEG_PATH` | FFmpeg 路径 |
| `VP_FFPROBE_PATH` | FFprobe 路径 |
| `VP_RIFE_MODEL_DIR` | 模型目录 |
| `VP_OUTPUT_DIR` | 默认输出目录 |
| `VP_LOG_DIR` | 日志目录 |

## 测试

```bash
cd backend
python -m pytest tests -q
```
