// pure: no Vue / no Pinia / no Tauri
// 默认值工厂 — 根据环境探测结果生成默认的解码/编码/工作流/输出/预设配置。

import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine } from '@/types/domain/workflow'
import { pickPreferredDecoderProfile, pickPreferredEncoderProfile } from './profile-picker'

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

export function createDefaultWorkbenchPreset(env: EnvironmentCheckResult | null): WorkbenchPreset {
  const workflowConfig = createDefaultWorkflowConfig()
  workflowConfig.interpolation.onnxModel = env?.onnxModels?.interpolation?.[0] ?? ''
  workflowConfig.superResolution.onnxModel = env?.onnxModels?.super_resolution?.[0] ?? ''

  const vendor = env?.gpu?.adapters?.[0]?.vendor
  const backend = workflowConfig.interpolation.tensorBackend
  const engines = (env?.tensorEngines as Record<string, string[]> | undefined)?.[backend] ?? []
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
