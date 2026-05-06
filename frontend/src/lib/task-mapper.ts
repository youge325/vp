import type {
  DecodeConfig,
  DecoderProfileSpec,
  EncodeConfig,
  EncoderProfileSpec,
  EnvironmentCheckResult,
  InferenceEngine,
  MediaItem,
  OutputConfig,
  ResumeMode,
  TaskError,
  TaskRequest,
  WorkbenchPreset,
  WorkflowConfig,
  WorkflowMode,
} from '@/types'

const FAMILY_PRIORITY = ['nvidia', 'intel', 'cpu'] as const
const CODEC_PRIORITY = ['hevc', 'h264', 'av1'] as const

export function resolvePrimaryMode(item: Pick<MediaItem, 'workflowConfig'>): WorkflowMode {
  const workflow = item.workflowConfig
  if (workflow.interpolation.enabled) {
    return 'frame_interpolation'
  }
  if (workflow.superResolution.enabled) {
    return 'super_resolution'
  }
  if (workflow.anime.enabled) {
    return 'anime_optimization'
  }
  return 'format_conversion'
}

export function createDefaultWorkflowConfig(): WorkflowConfig {
  return {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: {
      enabled: true,
      targetFps: 60,
      multi: 2,
      model: '4.25',
      onnxModel: '',
      scale: 1,
      fp16: false,
      tensorBackend: 'pytorch',
      engine: 'cuda',
    },
    superResolution: {
      enabled: false,
      scaleFactor: 2,
      algorithm: 'placeholder',
      onnxModel: '',
    },
    anime: {
      enabled: false,
      profile: 'clean-lines',
      denoise: 10,
      edgeBoost: 15,
    },
    preprocess: {
      enabled: false,
      filters: [],
    },
    postprocess: {
      enabled: false,
      filters: [],
    },
  }
}

export function createDefaultOutputConfig(outputDir = ''): OutputConfig {
  return {
    outputDir,
    openOnComplete: true,
    segmentFrames: 1000,
  }
}

export function createDefaultDecodeConfig(
  env: EnvironmentCheckResult | null,
  videoCodec = '',
): DecodeConfig {
  const decoder = pickPreferredDecoderProfile(env, videoCodec)
  if (!decoder || decoder.family === 'software') {
    return {
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
      options: {},
    }
  }

  return {
    mode: 'hardware',
    hwaccel: decoder.family === 'nvidia' ? 'cuda' : 'qsv',
    hwaccelDevice: '',
    decoder: decoder.name,
    options: {},
  }
}

export function createDefaultEncodeConfig(env: EnvironmentCheckResult | null): EncodeConfig {
  const profile = pickPreferredEncoderProfile(env)
  const codec = profile?.name ?? 'libx265'
  const family: EncodeConfig['family'] =
    profile?.family === 'nvidia' || profile?.family === 'intel' ? profile.family : 'cpu'
  const options: Record<string, string | number | boolean> = {}
  const presetOption = profile?.options.find((option) => option.name === 'preset')
  if (presetOption?.defaultValue != null) {
    options.preset = presetOption.defaultValue
  } else if (presetOption?.choices.length) {
    options.preset = presetOption.choices[0]?.value ?? 'medium'
  } else {
    options.preset = family === 'cpu' ? 'medium' : 'p4'
  }

  return {
    codec,
    family,
    container: 'mp4',
    keepAudio: true,
    rateControl: {
      mode: family === 'cpu' ? 'crf' : family === 'nvidia' ? 'cq' : 'qp',
      value: family === 'cpu' ? 18 : 23,
    },
    options,
  }
}

export function getEncoderProfiles(env: EnvironmentCheckResult | null): EncoderProfileSpec[] {
  return env?.ffmpeg.encoderProfiles ?? []
}

export function getDecoderProfiles(env: EnvironmentCheckResult | null): DecoderProfileSpec[] {
  return env?.ffmpeg.decoderProfiles ?? []
}

export function getVisibleEncoderProfiles(env: EnvironmentCheckResult | null): EncoderProfileSpec[] {
  return getEncoderProfiles(env).filter((profile) => profile.available)
}

export function getVisibleDecoderProfiles(
  env: EnvironmentCheckResult | null,
  videoCodec = '',
): DecoderProfileSpec[] {
  const codec = normalizeCodec(videoCodec)
  return getDecoderProfiles(env).filter((profile) => {
    if (!profile.available) {
      return false
    }
    return profile.codec === 'any' || !codec || profile.codec === codec
  })
}

export function buildTaskRequest(item: MediaItem, resumeMode?: ResumeMode): TaskRequest {
  return {
    inputPath: item.inputPath,
    decodeConfig: item.decodeConfig,
    workflowConfig: item.workflowConfig,
    encodeConfig: item.encodeConfig,
    outputConfig: item.outputConfig,
    ...(resumeMode ? { resumeMode } : {}),
  }
}

export function createDefaultWorkbenchPreset(env: EnvironmentCheckResult | null): WorkbenchPreset {
  const workflowConfig = createDefaultWorkflowConfig()
  workflowConfig.interpolation.onnxModel = env?.onnx_models?.interpolation?.[0] ?? ''
  workflowConfig.superResolution.onnxModel = env?.onnx_models?.super_resolution?.[0] ?? ''

  // 根据 GPU 类型设置默认推理引擎
  const vendor = env?.gpu?.adapters?.[0]?.vendor
  const backend = workflowConfig.interpolation.tensorBackend
  const engines = (env?.tensor_engines as Record<string, string[]> | undefined)?.[backend] ?? []
  if (vendor === 'hygon') {
    workflowConfig.interpolation.engine = engines.includes('dcu') ? 'dcu' : (engines[0] as InferenceEngine) ?? 'cuda'
  } else if (vendor === 'nvidia') {
    workflowConfig.interpolation.engine = engines.includes('tensorrt') ? 'tensorrt' : (engines[0] as InferenceEngine) ?? 'cuda'
  } else {
    workflowConfig.interpolation.engine = (engines[0] as InferenceEngine) ?? 'cuda'
  }

  return {
    decodeConfig: createDefaultDecodeConfig(env),
    workflowConfig,
    encodeConfig: createDefaultEncodeConfig(env),
    outputConfig: createDefaultOutputConfig(),
  }
}

export function formatNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }
  return value.toFixed(2).replace(/\.?0+$/, '')
}

export function cloneWorkflowConfig(config: WorkflowConfig): WorkflowConfig {
  return JSON.parse(JSON.stringify(config)) as WorkflowConfig
}

export function cloneEncodeConfig(config: EncodeConfig): EncodeConfig {
  return JSON.parse(JSON.stringify(config)) as EncodeConfig
}

export function cloneDecodeConfig(config: DecodeConfig): DecodeConfig {
  return JSON.parse(JSON.stringify(config)) as DecodeConfig
}

export function cloneOutputConfig(config: OutputConfig): OutputConfig {
  return JSON.parse(JSON.stringify(config)) as OutputConfig
}

export function cloneWorkbenchPreset(config: WorkbenchPreset): WorkbenchPreset {
  return JSON.parse(JSON.stringify(config)) as WorkbenchPreset
}

function pickPreferredEncoderProfile(env: EnvironmentCheckResult | null): EncoderProfileSpec | null {
  const profiles = getVisibleEncoderProfiles(env)
  for (const family of FAMILY_PRIORITY) {
    const familyProfiles = profiles.filter((profile) => profile.family === family)
    if (familyProfiles.length === 0) {
      continue
    }
    for (const codec of CODEC_PRIORITY) {
      const match = familyProfiles.find((profile) => profile.codec === codec)
      if (match) {
        return match
      }
    }
    return familyProfiles[0] ?? null
  }
  return null
}

function pickPreferredDecoderProfile(
  env: EnvironmentCheckResult | null,
  videoCodec: string,
): DecoderProfileSpec | null {
  const codec = normalizeCodec(videoCodec)
  const profiles = getVisibleDecoderProfiles(env, codec)
  for (const family of ['nvidia', 'intel'] as const) {
    const match = profiles.find((profile) => profile.family === family)
    if (match) {
      return match
    }
  }
  return profiles.find((profile) => profile.family === 'software') ?? null
}

function normalizeCodec(codec: string): string {
  const lowered = codec.toLowerCase()
  if (lowered.includes('hevc') || lowered.includes('h265')) {
    return 'hevc'
  }
  if (lowered.includes('av1')) {
    return 'av1'
  }
  if (lowered.includes('h264') || lowered.includes('avc')) {
    return 'h264'
  }
  return lowered
}

export function normalizeTaskError(error: unknown, code = 'runtime_error'): TaskError {
  if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
    const payload = error as { code?: unknown; message?: unknown; details?: Record<string, unknown> | null }
    return {
      code: typeof payload.code === 'string' ? payload.code : code,
      message: typeof payload.message === 'string' ? payload.message : 'Execution failed.',
      details: payload.details ?? null,
    }
  }

  if (error instanceof Error) {
    return { code, message: error.message, details: null }
  }

  return { code, message: String(error), details: null }
}
