# Backend CLI

后端当前只保留正式 CLI 与流式处理链路，不再保留旧的临时帧落盘 pipeline，也不再暴露历史 `decoder.py` / `encoder.py` / `frame_processor.py` / `pipeline.py` 结构。

## 命令入口

```powershell
cd backend

python -m app check
python -m app info --input D:\path\to\video.mp4
python -m app process --input D:\path\to\video.mp4
```

- `check`：检查 FFmpeg、GPU、模型和运行时能力
- `info`：读取输入视频元数据
- `process`：执行流式处理或纯转码

## `process` 的配置输入

桌面工作台当前通过四段 JSON 把完整配置传给 CLI：

- `--decode-config-json`
- `--workflow-config-json`
- `--encode-config-json`
- `--output-config-json`

示例：

```powershell
python -m app process `
  --input D:\input\demo.mp4 `
  --decode-config-json '{"mode":"hardware","hwaccel":"cuda","decoder":"hevc_cuvid","options":{}}' `
  --workflow-config-json '{"fpsMode":"target","processOrder":"frame_interpolation_then_super_resolution","interpolation":{"enabled":true,"targetFps":60,"multi":2,"model":"4.25","scale":1,"fp16":false,"tensorBackend":"pytorch"},"superResolution":{"enabled":false,"scaleFactor":2,"algorithm":"placeholder"},"anime":{"enabled":false,"profile":"clean-lines","denoise":10,"edgeBoost":15}}' `
  --encode-config-json '{"codec":"hevc_nvenc","family":"nvidia","container":"mp4","keepAudio":true,"rateControl":{"mode":"cq","value":23},"options":{"preset":"p4"}}' `
  --output-config-json '{"outputDir":"D:\\output","openOnComplete":false,"segmentFrames":1000}'
```

## 当前处理模型

- 有处理步骤时：解码、算法处理、编码全部走内存中的流式链路
- 纯 `format_conversion` 时：直接调用 FFmpeg 转码
- 开启补帧时：按 `outputConfig.segmentFrames` 分段输出中间结果，全部完成后自动拼接并回封音频

## 输出事件

CLI 通过 stdout 逐行输出 JSON，桌面端按行消费：

```json
{"type":"progress","current":120,"total":480,"percent":25.0,"stage":"Frame Interpolation","stage_index":1,"stage_total":2}
{"type":"completed","output_path":"D:/output/demo_processed.mp4","processed_frames":960,"time_seconds":42.7}
```

失败时输出：

```json
{"type":"error","code":"process_failed","message":"...","details":{}}
```

## 关键环境变量

- `VP_APP_ROOT`
- `VP_RUNTIME_ROOT`
- `VP_PYTHON_EXECUTABLE`
- `VP_FFMPEG_PATH`
- `VP_FFPROBE_PATH`
- `VP_RIFE_MODEL_DIR`
- `VP_OUTPUT_DIR`
- `VP_LOG_DIR`

## 测试

```powershell
cd backend
python -m pytest tests -q
```
