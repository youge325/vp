// pure: no Vue / no Pinia / no Tauri
// Selection helpers backing enhance workflow mutation rules.

import type { EnvironmentCheckResult } from '@/types/protocol'
import type { TensorBackend } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import {
  fixedRuntimeFrameCount,
  fixedSuperResolutionScaleFactor,
} from './enhance-algorithm-capabilities'
import {
  pickDefaultInterpolationAlgorithm,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-algorithm-defaults'
import { pickDefaultEngine } from './enhance-engine-defaults'
import { pickDefaultInterpolationModel } from './enhance-metadata-defaults'
import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
} from './enhance-onnx-defaults'
import { applySuperResolutionAlgorithmDefaults } from './enhance-super-resolution-defaults'
import {
  findInterpolationAlgorithm,
  findSuperResolutionAlgorithm,
  pickSupportedBackend,
} from './enhance-workflow-lookup'

export function preferOnnxInterpolationForPaddleSuperResolution(
  config: WorkflowConfig,
  checkResult: EnvironmentCheckResult | null,
): void {
  if (
    !config.interpolation.enabled ||
    !config.superResolution.enabled ||
    config.superResolution.tensorBackend !== 'paddle' ||
    config.interpolation.tensorBackend !== 'pytorch'
  ) {
    return
  }

  const backend: TensorBackend = 'onnx'
  const algorithm = pickDefaultInterpolationAlgorithm(checkResult, backend)
  config.interpolation.tensorBackend = backend
  config.interpolation.engine = pickDefaultEngine(checkResult, backend) ?? config.interpolation.engine
  config.interpolation.algorithm = algorithm
  config.interpolation.model = pickDefaultInterpolationModel(checkResult, algorithm)
  config.interpolation.onnxModel = fallbackInterpolationOnnxModel(
    checkResult,
    algorithm,
    '',
  )
}

export function applyInterpolationBackendSelectionDefaults(
  config: WorkflowConfig,
  value: TensorBackend,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.interpolation.tensorBackend = value
  config.interpolation.engine = pickDefaultEngine(checkResult, value) ?? config.interpolation.engine

  const supportsCurrent = findInterpolationAlgorithm(checkResult, config.interpolation.algorithm)
    ?.tensorBackends?.includes(value) ?? false
  if (!supportsCurrent) {
    const next = pickDefaultInterpolationAlgorithm(checkResult, value)
    config.interpolation.algorithm = next
    config.interpolation.model = pickDefaultInterpolationModel(checkResult, next)
  }

  if (value === 'onnx') {
    config.interpolation.onnxModel = fallbackInterpolationOnnxModel(
      checkResult,
      config.interpolation.algorithm,
      config.interpolation.onnxModel,
    )
  }
}

export function applyInterpolationAlgorithmSelectionDefaults(
  config: WorkflowConfig,
  value: string,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.interpolation.algorithm = value
  config.interpolation.model = pickDefaultInterpolationModel(checkResult, value)
}

export function applySuperResolutionBackendSelectionDefaults(
  config: WorkflowConfig,
  value: TensorBackend,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.tensorBackend = value
  config.superResolution.engine = pickDefaultEngine(checkResult, value) ?? config.superResolution.engine

  const supportsCurrent = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
    ?.tensorBackends?.includes(value) ?? false
  if (!supportsCurrent) {
    config.superResolution.algorithm = pickDefaultSuperResolutionAlgorithm(checkResult, value)
  }

  const algorithm = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
  applySuperResolutionAlgorithmDefaults(config, algorithm, checkResult)

  if (value === 'onnx') {
    config.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
      checkResult,
      config.superResolution.algorithm,
      config.superResolution.onnxModel,
    )
  }

  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function applySuperResolutionAlgorithmSelectionDefaults(
  config: WorkflowConfig,
  value: string,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.algorithm = value
  const algorithm = findSuperResolutionAlgorithm(checkResult, value)
  const backend = pickSupportedBackend(algorithm, config.superResolution.tensorBackend as TensorBackend)
  config.superResolution.tensorBackend = backend
  config.superResolution.engine = pickDefaultEngine(checkResult, backend) ?? config.superResolution.engine
  applySuperResolutionAlgorithmDefaults(config, algorithm, checkResult)
  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function resolveSuperResolutionScale(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): number {
  const algorithm = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
  return fixedSuperResolutionScaleFactor(algorithm) ?? value
}

export function resolveSuperResolutionNumFrames(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): number {
  const algorithm = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
  return fixedRuntimeFrameCount(algorithm) ?? value
}
