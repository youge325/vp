// pure: no Vue / no Pinia / no Tauri
// Default workflow config and environment hydration rules.

import { APPLICATION_DEFAULTS, type EnvironmentCheckResult, type WorkflowConfig } from '@/types/protocol'
import {
  pickDefaultSuperResolutionAlgorithm,
  pickDefaultInterpolationAlgorithm,
} from './enhance-algorithm-defaults'
import { pickDefaultEngine, pickDefaultInterpolationEngine } from './enhance-engine-defaults'
import { pickDefaultInterpolationModel } from './enhance-metadata-defaults'
import { fallbackInterpolationOnnxModel, fallbackSuperResolutionOnnxModel } from './enhance-onnx-defaults'
import { applySuperResolutionAlgorithmDefaults } from './enhance-super-resolution-defaults'
import { findSuperResolutionAlgorithm } from './enhance-workflow-lookup'

function createDefaultWorkflowConfig(): WorkflowConfig {
  const { interpolation, superResolution, workflow } = APPLICATION_DEFAULTS
  return {
    fpsMode: workflow.desktopFpsMode,
    processOrder: workflow.processOrder,
    interpolation: {
      enabled: true,
      targetFps: interpolation.targetFps,
      multi: interpolation.multi,
      algorithm: interpolation.algorithm,
      model: interpolation.model,
      onnxModel: interpolation.onnxModel,
      scale: interpolation.scale,
      fp16: interpolation.fp16,
      tensorBackend: interpolation.tensorBackend,
      engine: interpolation.engine,
    },
    superResolution: {
      enabled: false,
      scaleFactor: superResolution.scaleFactor,
      algorithm: superResolution.algorithm,
      onnxModel: superResolution.onnxModel,
      tensorBackend: superResolution.tensorBackend,
      engine: superResolution.engine,
      numFrames: superResolution.numFrames,
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

  workflowConfig.interpolation.engine = pickDefaultInterpolationEngine(env, interpolationBackend)
    ?? APPLICATION_DEFAULTS.interpolation.engine
  workflowConfig.superResolution.engine = pickDefaultEngine(env, superResolutionBackend)
    ?? APPLICATION_DEFAULTS.superResolution.engine
}

export function createDefaultWorkflowConfigForEnvironment(
  env: EnvironmentCheckResult | null,
): WorkflowConfig {
  const workflowConfig = createDefaultWorkflowConfig()
  applyEnvironmentWorkflowDefaults(workflowConfig, env)
  return workflowConfig
}
