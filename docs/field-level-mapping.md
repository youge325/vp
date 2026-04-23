# 字段级映射图

这张图聚焦关键字段如何从前端对象映射到后端执行参数，以及它们在流式执行和分段输出中的落点。

```mermaid
graph LR
  subgraph FE[前端 TaskRequest 字段]
    FEInput[inputPath]
    FEDecode[decodeConfig mode hwaccel hwaccelDevice decoder options]
    FEWorkflow[workflowConfig fpsMode processOrder interpolation targetFps multi]
    FEEncode[encodeConfig codec container keepAudio rateControl options]
    FEOutput[outputConfig outputDir openOnComplete segmentFrames]
  end

  subgraph RS[Rust 构建 CLI]
    RSIn[--input]
    RSD[--decode-config-json]
    RSW[--workflow-config-json]
    RSE[--encode-config-json]
    RSO[--output-config-json]
  end

  subgraph PY[Python 解析与执行]
    PYIn[args.input]
    PYD[_load_json_arg -> decode_config]
    PYW[_load_json_arg -> workflow_config]
    PYE[_load_json_arg -> encode_config]
    PYO[_load_json_arg -> output_config]
    PYExec[streaming executor 或 transcode_video]
  end

  subgraph FF[FFmpeg 参数落点]
    FFD[-hwaccel -hwaccel_device -c:v -key value]
    FFW[source_fps target_fps multi output_fps]
    FFE[-c:v -crf cq qp b:v -key value]
    FFO[output_path segmentFrames keep_audio concat merge]
  end

  FEInput --> RSIn --> PYIn
  FEDecode --> RSD --> PYD --> FFD
  FEWorkflow --> RSW --> PYW --> FFW
  FEEncode --> RSE --> PYE --> FFE
  FEOutput --> RSO --> PYO --> FFO

  PYW --> PYExec
  PYE --> PYExec
  PYO --> PYExec
```

关键映射示例：

- `decodeConfig.hwaccelDevice` -> `decode_config.hwaccelDevice` -> `-hwaccel_device`
- `decodeConfig.options` -> `decode_config.options` -> 解码器附加参数
- `encodeConfig.rateControl.mode/value` -> `rateControl` -> `-crf` / `-cq` / `-qp` / `-b:v`
- `encodeConfig.options` -> `encode_config.options` -> 编码器附加参数
- `workflowConfig.interpolation.targetFps` 与 `workflowConfig.interpolation.multi` -> 流程内部计算 -> 流式编码 `fps/output_fps`
- `outputConfig.segmentFrames` -> 分段 sidecar / manifest -> 分段拼接与断点恢复
