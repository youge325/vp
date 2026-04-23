# 参数传递架构图

这张图描述当前流式处理链路中，前端配置如何经过 Tauri 和 Python CLI，最终驱动 `decoder -> processor -> encoder` 的内存管道与分段输出。

```mermaid
graph TD
  subgraph FE[Vue 前端]
    FEView[Decode Enhance Deliver 视图]
    FEStore[Pinia workbench store]
    FEReq[buildTaskRequest 生成 TaskRequest]
  end

  subgraph IPC[Tauri IPC]
    FEInvoke[invoke start_task request]
    RSCommand[tauri command start_task]
    RSModel[models TaskRequest serde camelCase]
  end

  subgraph RT[Rust Runtime]
    RSBuild[build_process_command]
    RSEnv[build_env_map]
    RSPython[spawn python -m app process]
  end

  subgraph PY[Python CLI]
    PYParser[argparse process 子命令]
    PYLoad[_load_json_arg 和默认配置合并]
    PYPlan[_resolve_processing_steps]
    PYExec[process_video_streaming 或 transcode_video]
  end

  subgraph Stream[Streaming Executor]
    SDecode[rawvideo decoder]
    SQueue1[decode queue maxsize=8]
    SProcess[pre stages + interpolation + post stages]
    SQueue2[encode queue maxsize=8]
    SEncode[rawvideo encoder]
    SSegment[segment manifest 和 sidecar]
    SFinalize[concat segments + merge audio]
  end

  subgraph FF[FFmpeg Wrapper]
    FFDecode[build_rawvideo_decode_command]
    FFEncode[build_rawvideo_encode_command]
    FFConcat[concat_videos]
    FFAudio[extract_audio / merge_audio]
    FFDirect[transcode_video]
    FFRun[_run_command]
  end

  ENV[VP_FFMPEG_PATH VP_FFPROBE_PATH VP_RIFE_MODEL_DIR]
  CFG[Settings env_prefix VP_]
  BIN[(ffmpeg / ffprobe)]

  FEView --> FEStore --> FEReq --> FEInvoke
  FEInvoke --> RSCommand --> RSModel --> RSBuild --> RSPython

  RSPython --> PYParser --> PYLoad --> PYPlan --> PYExec

  PYExec -->|有处理阶段| SDecode
  SDecode --> SQueue1 --> SProcess --> SQueue2 --> SEncode --> SSegment --> SFinalize
  PYExec -->|纯转码| FFDirect

  SDecode --> FFDecode --> FFRun
  SEncode --> FFEncode --> FFRun
  SFinalize --> FFConcat --> FFRun
  SFinalize --> FFAudio --> FFRun
  FFDirect --> FFRun --> BIN

  RSEnv -. 注入 VP_* .-> RSPython
  ENV -. runtime resolve .-> RSEnv
  RSPython -. 读取环境变量 .-> CFG
  CFG -. 设置 FFMPEG_PATH / FFPROBE_PATH .-> FFRun
```

说明：

- 有帧处理阶段的任务统一走流式执行器，不再经过临时帧目录。
- 解码和编码都通过 FFmpeg `rawvideo` 管道完成，中间只保留有界队列中的少量帧。
- `segmentFrames` 控制分段输出，分段仅作为恢复缓存；任务最终完成后会拼接成单个成片。
- 纯 `format_conversion` 不走补帧流式处理，直接走 FFmpeg 转码/封装。
