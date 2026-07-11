// 领域层 — 环境探测领域模型(GPU 适配器、能力探测结果、应用环境状态)。

import type { TaskError } from './media'
import type { EnvironmentCheckSource, GpuDeviceType, GpuVendor } from './workflow'
import type { DecoderProfileSpec, EncoderProfileSpec } from './capability'

export interface GpuAdapter {
  name: string
  vendor: GpuVendor
  deviceType: GpuDeviceType
  adapterCompatibility?: string
  driverVersion?: string
}

type ModelAnalysisStatus = 'ok' | 'partial' | 'unknown' | string

export interface ModelEngineMetricInfo {
  gflopsPerMegapixel?: number | null
  activationBytesPerMegapixel?: number | null
  runtimeOverheadBytes?: number | null
  runtimeFrameCount?: number | null
  inputModulo?: number | null
  analysisStatus?: ModelAnalysisStatus
  analysisNotes?: string[]
}

interface ModelMetricInfo {
  parameterCount?: number | null
  parameterBytes?: number | null
  gflopsPerMegapixel?: number | null
  activationBytesPerMegapixel?: number | null
  runtimeOverheadBytes?: number | null
  runtimeFrameCount?: number | null
  inputModulo?: number | null
  analysisStatus: ModelAnalysisStatus
  analysisNotes: string[]
  engineMetrics?: Record<string, ModelEngineMetricInfo>
}

export interface ModelVariantInfo {
  name: string
  label: string
  metrics: ModelMetricInfo
}

export interface AlgorithmInfo {
  name: string
  family?: 'rife' | 'onnx_super_resolution' | 'paddlegan_vsr' | string | null
  tensorBackends: string[]
  models: string[]
  onnxModels?: string[]
  modelDetails?: ModelVariantInfo[]
  onnxModelDetails?: ModelVariantInfo[]
  scaleFactors?: number[]
  fixedScaleFactor?: number | null
  defaultNumFrames?: number | null
  sequenceMode?: 'recurrent' | 'window' | string | null
  inputFrameMode?: 'none' | 'editable_chunk' | 'fixed_window' | string | null
}

export interface EnvironmentCheckResult {
  ffmpeg: {
    available: boolean
    hwaccels: string[]
    encoderProfiles: EncoderProfileSpec[]
    decoderProfiles: DecoderProfileSpec[]
  }
  gpu: {
    adapters: GpuAdapter[]
  }
  tensorEngines: {
    pytorch: string[]
    paddle: string[]
    onnx: string[]
  }
  backendDeviceSupport: {
    pytorch: string[]
    paddle: string[]
    onnx: string[]
  }
  // Phase 8 — ``tensorBackends`` 由 Rust ``AlgorithmInfo`` 字段透出,
  // 前端按 ``workflow.interpolation.tensorBackend`` 过滤算法下拉。
  // 旧缓存反序列化时 ``tensorBackends`` 不存在 → 退化为 ``[]``,
  // 在 ``useEnhanceForm`` 的 ``.includes(backend)`` 上返回 false
  // (不显示),比错显示安全。
  interpolationAlgorithms: AlgorithmInfo[]
  superResolutionAlgorithms: AlgorithmInfo[]
  runtimeMode: string
}

export interface EnvironmentCheckPayload {
  result: EnvironmentCheckResult
  source: EnvironmentCheckSource
  checkedAt: string | null
}

export interface AppEnv {
  lastCheckedAt: string | null
  lastProbeAt: string | null
  checkSource: EnvironmentCheckSource | null
  isChecking: boolean
  isBootstrapping: boolean
  checkResult: EnvironmentCheckResult | null
  issue: TaskError | null
}
