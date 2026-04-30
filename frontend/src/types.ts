import type { Component } from 'vue'

export type WorkflowMode =
  | 'frame_interpolation'
  | 'super_resolution'
  | 'anime_optimization'
  | 'format_conversion'

export type ModuleKey = 'home' | 'input' | 'decode' | 'enhance' | 'encode' | 'render'
export type ProcessOrder =
  | 'super_resolution_then_interpolation'
  | 'frame_interpolation_then_super_resolution'
export type FpsMode = 'multi' | 'target'
export type TensorBackend = 'pytorch' | 'paddle' | 'onnx'
export type TaskStatus = 'idle' | 'running' | 'paused' | 'cancelling' | 'completed' | 'error' | 'cancelled'
export type CodecFamily = 'cpu' | 'nvidia' | 'intel' | 'software'
export type GpuVendor = 'nvidia' | 'intel' | 'amd' | 'hygon' | 'other'
export type GpuDeviceType = 'integrated' | 'discrete' | 'virtual' | 'other'
export type InferenceEngine = 'cuda' | 'tensorrt' | 'dcu'
export type CapabilityValue = string | number | boolean
export type CapabilityOptionType = 'boolean' | 'number' | 'string' | 'choice'
export type RateControlMode = 'crf' | 'cq' | 'qp' | 'bitrate'
export type EnvironmentCheckSource = 'cache' | 'probe'
export type EditingScope = 'preset' | 'selection'

export interface CapabilityChoice {
  label: string
  value: CapabilityValue
}

export interface CapabilityOptionSpec {
  name: string
  label: string
  type: CapabilityOptionType
  defaultValue: CapabilityValue | null
  choices: CapabilityChoice[]
  min: number | null
  max: number | null
}

export interface CodecProfileSpec {
  name: string
  label: string
  family: CodecFamily
  codec: string
  available: boolean
  pixelFormats: string[]
  hardwareDevices: string[]
  options: CapabilityOptionSpec[]
}

export interface EncoderProfileSpec extends CodecProfileSpec {}
export interface DecoderProfileSpec extends CodecProfileSpec {}

export interface GpuAdapter {
  name: string
  vendor: GpuVendor
  deviceType: GpuDeviceType
  adapterCompatibility?: string
  driverVersion?: string
}

export interface ResourceSummary {
  backend_root?: string
  runtime_root?: string
  runtime_mode?: string
  python_executable?: string
  ffmpeg_path?: string
  ffprobe_path?: string
  default_model_path?: string
  [key: string]: string | boolean | number | null | undefined
}

export interface EnvironmentCheckResult {
  type: 'check'
  ffmpeg: {
    available?: boolean
    version?: string
    path?: string
    ffprobe_path?: string
    hwaccels: string[]
    encoderProfiles: EncoderProfileSpec[]
    decoderProfiles: DecoderProfileSpec[]
  }
  gpu: {
    available?: boolean
    devices: string[]
    adapters: GpuAdapter[]
    cuda_available?: boolean
  }
  tensor_backends: {
    pytorch?: boolean
    paddle?: boolean
    onnx?: boolean
  }
  tensor_engines?: {
    pytorch?: string[]
    paddle?: string[]
    onnx?: string[]
  }
  backend_device_support?: {
    pytorch?: string[]
    paddle?: string[]
    onnx?: string[]
  }
  onnx_runtime?: {
    available?: boolean
    providers: string[]
  }
  onnx_models?: {
    interpolation: string[]
    super_resolution: string[]
  }
  rife_model: {
    available?: boolean
    version?: string
    path?: string
  }
  runtime?: {
    mode?: string
    bundled?: boolean
    python_executable?: string
    default_model_available?: boolean
  }
  resources?: ResourceSummary
}

export interface EnvironmentCheckPayload {
  result: EnvironmentCheckResult
  source: EnvironmentCheckSource
  checkedAt: string | null
}

export interface TaskError {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export type OperationIssueScope = 'input' | 'encode' | 'output' | 'task'

export interface OperationIssue {
  scope: OperationIssueScope
  error: TaskError
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

export interface VideoInfoResult {
  type: 'info'
  fps: number
  frames: number
  duration: number
  width: number
  height: number
  has_audio: boolean
  video_codec: string
}

export interface DecodeConfig {
  mode: 'software' | 'hardware'
  hwaccel: string
  hwaccelDevice: string
  decoder: string
  options: Record<string, CapabilityValue>
}

export interface InterpolationConfig {
  enabled: boolean
  targetFps: number
  multi: number
  model: string
  onnxModel?: string
  scale: number
  fp16: boolean
  tensorBackend: TensorBackend
  engine?: InferenceEngine
}

export interface SuperResolutionConfig {
  enabled: boolean
  scaleFactor: number
  algorithm: string
  onnxModel?: string
}

export interface AnimeConfig {
  enabled: boolean
  profile: string
  denoise: number
  edgeBoost: number
}

export interface WorkflowConfig {
  fpsMode: FpsMode
  processOrder: ProcessOrder
  interpolation: InterpolationConfig
  superResolution: SuperResolutionConfig
  anime: AnimeConfig
}

export interface RateControlConfig {
  mode: RateControlMode
  value: number
}

export interface EncodeConfig {
  codec: string
  family: Exclude<CodecFamily, 'software'>
  container: string
  keepAudio: boolean
  rateControl: RateControlConfig
  options: Record<string, CapabilityValue>
}

export interface OutputConfig {
  outputDir: string
  openOnComplete: boolean
  segmentFrames: number
}

export interface WorkbenchPreset {
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
}

export interface MediaTaskState {
  status: TaskStatus
  percent: number
  current: number
  total: number
  stage: string
  stageIndex: number
  stageTotal: number
  logs: string[]
  outputPath: string
  processedFrames: number
  timeSeconds: number
  error: TaskError | null
  startedAt: string | null
  finishedAt: string | null
}

export interface MediaItem {
  id: string
  inputPath: string
  displayName: string
  selected: boolean
  inspecting: boolean
  info: VideoInfoResult | null
  issue: TaskError | null
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
  taskState: MediaTaskState
  lastOutputPath: string
}

export interface BatchState {
  queue: string[]
  currentId: string | null
  completedCount: number
  failedCount: number
  isRunning: boolean
  isPaused: boolean
  isCancelling: boolean
}

export interface TaskProgressPayload {
  current?: number
  total?: number
  percent?: number
  stage?: string
  stageIndex?: number
  stageTotal?: number
}

export interface TaskCompletedPayload {
  outputPath?: string
  processedFrames?: number
  timeSeconds?: number
}

export interface TaskLogPayload {
  message: string
}

export interface TaskRequest {
  inputPath: string
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
}

export interface WorkbenchModuleDefinition {
  key: ModuleKey
  title: string
  path: string
  description: string
  icon: Component
}
