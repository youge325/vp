export type WorkflowMode =
  | 'frame_interpolation'
  | 'super_resolution'
  | 'anime_optimization'
  | 'format_conversion'

export type StageKey = 'prepare' | 'enhance' | 'deliver' | 'results'
export type ProcessOrder =
  | 'super_resolution_then_interpolation'
  | 'frame_interpolation_then_super_resolution'

export type FpsMode = 'multi' | 'target'
export type TensorBackend = 'pytorch' | 'paddle'
export type TaskStatus = 'idle' | 'running' | 'completed' | 'error' | 'cancelled'

export interface AppEnv {
  lastCheckedAt: string | null
  isChecking: boolean
  checkResult: EnvironmentCheckResult | null
  issue: TaskError | null
}

export interface SourceMedia {
  inputPath: string
  inspecting: boolean
  info: VideoInfoResult | null
}

export interface WorkflowSelection {
  primaryMode: WorkflowMode
  enableInterpolation: boolean
  enableSuperResolution: boolean
  processOrder: ProcessOrder
  fpsMode: FpsMode
}

export interface InterpolationSettings {
  targetFps: number
  multi: number
  model: string
  scale: number
  fp16: boolean
  tensorBackend: TensorBackend
}

export interface SuperResolutionSettings {
  enabled: boolean
  scaleFactor: number
  algorithm: string
}

export interface AnimeOptimizationSettings {
  enabled: boolean
  profile: string
  denoise: number
  edgeBoost: number
}

export interface FormatConversionSettings {
  remuxOnly: boolean
  keepAudio: boolean
  container: string
}

export interface EncodeSettings {
  codec: string
  crf: number
  preset: string
}

export interface OutputSettings {
  outputPath: string
  outputDir: string
  tempDir: string
  openOnComplete: boolean
}

export interface TaskError {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export interface TaskRuntimeState {
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
  }
  gpu: {
    available?: boolean
    devices?: string[]
  }
  tensor_backends: {
    pytorch?: boolean
    paddle?: boolean
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

export interface VideoInfoResult {
  type: 'info'
  fps: number
  frames: number
  duration: number
  width: number
  height: number
  has_audio: boolean
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
  algorithm: WorkflowMode
  outputPath?: string
  outputDir?: string
  tempDir?: string
  fps: number
  fpsMode: FpsMode
  targetFps?: number
  codec: string
  crf: number
  preset: string
  backend: TensorBackend
  multi: number
  model: string
  scale: number
  fp16: boolean
  enableInterpolation: boolean
  enableSuperResolution: boolean
  processOrder: ProcessOrder
  srScaleFactor: number
  srAlgorithm: string
}

export interface WorkbenchStateSnapshot {
  env: AppEnv
  source: SourceMedia
  workflow: WorkflowSelection
  interpolation: InterpolationSettings
  superResolution: SuperResolutionSettings
  anime: AnimeOptimizationSettings
  format: FormatConversionSettings
  encode: EncodeSettings
  output: OutputSettings
  task: TaskRuntimeState
}

export interface StepDefinition {
  key: string
  index: number
  title: string
  path: string
  subtitle: string
  stage: StageKey
  tab: string
}

export interface StageDefinition {
  key: StageKey
  index: number
  title: string
  path: string
}

export interface StageTabDefinition {
  key: string
  label: string
}
