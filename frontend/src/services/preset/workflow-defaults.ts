// pure: no Vue / no Pinia / no Tauri
// Default workflow config and environment hydration rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  pickDefaultSuperResolutionAlgorithm,
  pickDefaultInterpolationAlgorithm,
} from './enhance-algorithm-defaults'
import { pickDefaultEngine, pickDefaultInterpolationEngine } from './enhance-engine-defaults'
import { pickDefaultAnimeProfile, pickDefaultInterpolationModel } from './enhance-metadata-defaults'
import { fallbackInterpolationOnnxModel, fallbackSuperResolutionOnnxModel } from './enhance-onnx-defaults'
import { applySuperResolutionAlgorithmDefaults } from './enhance-super-resolution-defaults'
import { findSuperResolutionAlgorithm } from './enhance-workflow-lookup'

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

function applyEnvironmentWorkflowDefaults(
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
    findSuperResolutionAlgorithm(env, workflowConfig.superResolution.algorithm),
    env,
  )
  workflowConfig.anime.profile = pickDefaultAnimeProfile(env)

  workflowConfig.interpolation.onnxModel = fallbackInterpolationOnnxModel(
    env,
    workflowConfig.interpolation.algorithm,
    undefined,
  )
  workflowConfig.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
    env,
    workflowConfig.superResolution.algorithm,
    undefined,
  )

  workflowConfig.interpolation.engine = pickDefaultInterpolationEngine(env, interpolationBackend) ?? 'cuda'
  workflowConfig.superResolution.engine = pickDefaultEngine(env, superResolutionBackend) ?? 'cuda'
}

export function createDefaultWorkflowConfigForEnvironment(
  env: EnvironmentCheckResult | null,
): WorkflowConfig {
  const workflowConfig = createDefaultWorkflowConfig()
  applyEnvironmentWorkflowDefaults(workflowConfig, env)
  return workflowConfig
}
