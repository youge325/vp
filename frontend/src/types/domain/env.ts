// 领域层 — 环境探测领域模型(GPU 适配器、能力探测结果、应用环境状态)。

import type { TaskError } from './media'
import type { EnvironmentCheckSource, GpuDeviceType, GpuVendor } from './workflow'
import type { DecoderProfileSpec, EncoderProfileSpec } from '../view/capability'

export interface GpuAdapter {
  name: string
  vendor: GpuVendor
  deviceType: GpuDeviceType
  adapterCompatibility?: string
  driverVersion?: string
}

export interface ResourceSummary {
  backendRoot?: string
  runtimeRoot?: string
  runtimeMode?: string
  pythonExecutable?: string
  ffmpegPath?: string
  ffprobePath?: string
  defaultModelPath?: string
  [key: string]: string | boolean | number | null | undefined
}

export interface EnvironmentCheckResult {
  type: 'check'
  ffmpeg: {
    available?: boolean
    version?: string
    path?: string
    ffprobePath?: string
    hwaccels: string[]
    encoderProfiles: EncoderProfileSpec[]
    decoderProfiles: DecoderProfileSpec[]
  }
  gpu: {
    available?: boolean
    devices: string[]
    adapters: GpuAdapter[]
    cudaAvailable?: boolean
  }
  tensorBackends: {
    pytorch?: boolean
    paddle?: boolean
    onnx?: boolean
  }
  tensorEngines?: {
    pytorch?: string[]
    paddle?: string[]
    onnx?: string[]
  }
  backendDeviceSupport?: {
    pytorch?: string[]
    paddle?: string[]
    onnx?: string[]
  }
  onnxRuntime?: {
    available?: boolean
    providers: string[]
  }
  onnxModels?: {
    interpolation: string[]
    super_resolution: string[]
  }
  rifeModel: {
    available?: boolean
    version?: string
    path?: string
  }
  runtime?: {
    mode?: string
    bundled?: boolean
    pythonExecutable?: string
    defaultModelAvailable?: boolean
  }
  resources?: ResourceSummary
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
