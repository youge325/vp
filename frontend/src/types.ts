import type { Component } from 'vue'
import type { DecodeConfig } from './types/generated/DecodeConfig'
import type { EncodeConfig } from './types/generated/EncodeConfig'
import type { OutputConfig } from './types/generated/OutputConfig'
import type { WorkflowConfig } from './types/generated/WorkflowConfig'

export type WorkflowMode =
  | 'frame_interpolation'
  | 'super_resolution'
  | 'anime_optimization'
  | 'format_conversion'

export type ModuleKey = 'home' | 'input' | 'decode' | 'preprocess' | 'enhance' | 'postprocess' | 'encode' | 'render'
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

export type FilterStepKind = 'scale' | 'crop' | 'pad' | 'sharpen' | 'denoise' | 'color'

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
  resumeStatus: ResumeStatus | null
}

export interface ResumeStatus {
  resumed: boolean
  completedChunks: number
  completedOutputFrames: number
  startSourceFrame: number
  totalOutputFrames: number
}

export type ResumeMode = 'auto' | 'force-fresh' | 'force-resume'

export interface ResumeInspectionResult {
  type: 'resume_inspection'
  pipeline_kind: 'streaming' | 'format_conversion'
  output_path: string
  input_path: string
  final_exists: boolean
  sidecar_exists: boolean
  signature_match: boolean
  completed_chunks: number
  completed_output_frames: number
  next_source_frame: number
  total_output_frames: number
}

export type ResumeConflictKind =
  | 'resume_available'
  | 'final_exists_with_resume'
  | 'final_exists_only'

export interface ResumeConflictDescriptor {
  itemId: string
  kind: ResumeConflictKind
  outputPath: string
  inspection: ResumeInspectionResult
}

export type ResumeConflictAction = 'resume' | 'fresh' | 'skip' | 'cancel'

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

export interface WorkbenchModuleDefinition {
  key: ModuleKey
  title: string
  path: string
  description: string
  icon: Component
}

// ---------------------------------------------------------------------------
// 从 Rust models 自动生成的 IPC 类型 —— 不要手工编辑
// 重新生成: cd frontend/src-tauri && cargo test
// ---------------------------------------------------------------------------
export type { AnimeConfig } from './types/generated/AnimeConfig'
export type { DecodeConfig }
export type { EncodeConfig }
export type { FilterStep } from './types/generated/FilterStep'
export type { InterpolationConfig } from './types/generated/InterpolationConfig'
export type { OutputConfig }
export type { PostprocessConfig } from './types/generated/PostprocessConfig'
export type { PreprocessConfig } from './types/generated/PreprocessConfig'
export type { RateControlConfig } from './types/generated/RateControlConfig'
export type { SuperResolutionConfig } from './types/generated/SuperResolutionConfig'
export type { TaskRequest } from './types/generated/TaskRequest'
export type { WorkbenchPreset } from './types/generated/WorkbenchPreset'
export type { WorkflowConfig }
