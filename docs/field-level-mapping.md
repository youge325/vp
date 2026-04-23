# 字段级映射图

该图聚焦关键字段如何从前端对象映射到后端解析结果，以及最终 ffmpeg 参数落点。

```mermaid
graph LR
  subgraph FE[前端 TaskRequest 字段]
    FEInput[inputPath]
    FEDecode[decodeConfig mode hwaccel hwaccelDevice decoder options]
    FEWorkflow[workflowConfig fpsMode processOrder interpolation targetFps multi]
    FEEncode[encodeConfig codec container keepAudio rateControl options]
    FEOutput[outputConfig outputDir openOnComplete]
  end

  subgraph RS[Rust 构建 CLI]
    RSIn[--input]
    RSD[--decode-config-json]
    RSW[--workflow-config-json]
    RSE[--encode-config-json]
    RSO[--output-config-json]
  end

  subgraph PY[Python 解析与处理]
    PYIn[args.input]
    PYD[_load_json_arg -> decode_config]
    PYW[_load_json_arg -> workflow_config]
    PYE[_load_json_arg -> encode_config]
    PYO[_load_json_arg -> output_config]
  end

  subgraph FF[FFmpeg 参数落点]
    FFD[-hwaccel -hwaccel_device -c:v -key value]
    FFW[fps multi target_fps 影响输出帧率]
    FFE[-c:v -crf cq qp b:v -key value]
    FFO[output_path container keep_audio audio merge]
  end

  FEInput --> RSIn --> PYIn
  FEDecode --> RSD --> PYD --> FFD
  FEWorkflow --> RSW --> PYW --> FFW
  FEEncode --> RSE --> PYE --> FFE
  FEOutput --> RSO --> PYO --> FFO

  PYW --> PYE
```

关键示例：

- decodeConfig.hwaccelDevice -> decode_config hwaccelDevice -> -hwaccel_device
- encodeConfig.rateControl.mode value -> rateControl -> -crf 或 -cq 或 -qp 或 -b:v
- decodeConfig.options 与 encodeConfig.options -> options -> -key value
- workflowConfig.interpolation.targetFps multi -> 流程内部计算 -> encode_from_frames fps output_fps
