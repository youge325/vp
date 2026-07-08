// pure: no Vue / no Pinia / no Tauri
// Default workflow config and environment hydration rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'
import {
  applySuperResolutionAlgorithmDefaults,
  pickDefaultAnimeProfile,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-rules'

export function createDefaultWorkflowConfig(): WorkflowConfig {
  return {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: {
      enabled: true,
      targetFps: 60,
      multi: 2,
      algorithm: 'rife',
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
      tensorBackend: 'onnx',
      engine: 'cuda',
      numFrames: 10,
      autoDownloadWeights: false,
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

export function applyEnvironmentWorkflowDefaults(
  workflowConfig: WorkflowConfig,
  env: EnvironmentCheckResult | null,
): void {
  const interpolationBackend = workflowConfig.interpolation.tensorBackend
  const algorithm = pickDefaultInterpolationAlgorithm(env, interpolationBackend)
  workflowConfig.interpolation.algorithm = algorithm
  workflowConfig.interpolation.model = pickDefaultInterpolationModel(env, algorithm)

  const superResolutionBackend = workflowConfig.superResolution.tensorBackend
  workflowConfig.superResolution.algorithm = pickDefaultSuperResolutionAlgorithm(
    env,
    superResolutionBackend,
  )
  applySuperResolutionAlgorithmDefaults(
    workflowConfig,
    env?.superResolutionAlgorithms?.find((a) => a.name === workflowConfig.superResolution.algorithm),
    env,
  )
  workflowConfig.anime.profile = pickDefaultAnimeProfile(env)

  workflowConfig.interpolation.onnxModel =
    env?.interpolationAlgorithms?.find((a) => a.name === workflowConfig.interpolation.algorithm)
      ?.onnxModels?.[0] ?? ''
  workflowConfig.superResolution.onnxModel =
    env?.superResolutionAlgorithms?.find((a) => a.name === workflowConfig.superResolution.algorithm)
      ?.onnxModels?.[0] ?? ''

  const vendor = env?.gpu?.adapters?.[0]?.vendor
  const engines = (env?.tensorEngines as Record<string, string[]> | undefined)?.[interpolationBackend] ?? []
  const superResolutionEngines =
    (env?.tensorEngines as Record<string, string[]> | undefined)?.[superResolutionBackend] ?? []
  if (vendor === 'hygon') {
    workflowConfig.interpolation.engine = engines.includes('dcu') ? 'dcu' : (engines[0] as InferenceEngine) ?? 'cuda'
  } else if (vendor === 'nvidia') {
    workflowConfig.interpolation.engine = engines.includes('tensorrt') ? 'tensorrt' : (engines[0] as InferenceEngine) ?? 'cuda'
  } else {
    workflowConfig.interpolation.engine = (engines[0] as InferenceEngine) ?? 'cuda'
  }
  workflowConfig.superResolution.engine = (superResolutionEngines[0] as InferenceEngine) ?? 'cuda'
}

export function createDefaultWorkflowConfigForEnvironment(
  env: EnvironmentCheckResult | null,
): WorkflowConfig {
  const workflowConfig = createDefaultWorkflowConfig()
  applyEnvironmentWorkflowDefaults(workflowConfig, env)
  return workflowConfig
}
