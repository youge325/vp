// pure: no Vue / no Pinia / no Tauri
// Workflow mutation rules for the enhance form.

import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'
import {
  applySuperResolutionAlgorithmDefaults,
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  fixedRuntimeFrameCount,
  fixedSuperResolutionScaleFactor,
  pickDefaultEngine,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-rules'

const TENSOR_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

function isTensorBackend(value: string): value is TensorBackend {
  return TENSOR_BACKENDS.includes(value as TensorBackend)
}

function findInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  name: string,
): AlgorithmInfo | undefined {
  return checkResult?.interpolationAlgorithms?.find((algorithm) => algorithm.name === name)
}

function findSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  name: string,
): AlgorithmInfo | undefined {
  return checkResult?.superResolutionAlgorithms?.find((algorithm) => algorithm.name === name)
}

function pickSupportedBackend(algorithm: AlgorithmInfo | undefined, fallback: TensorBackend): TensorBackend {
  if (!algorithm) return fallback
  if (algorithm.tensorBackends.includes(fallback)) return fallback
  return algorithm.tensorBackends.find(isTensorBackend) ?? fallback
}

function preferOnnxInterpolationForPaddleSuperResolution(
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

export function applyInterpolationEnabled(
  config: WorkflowConfig,
  value: boolean,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.interpolation.enabled = value
  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function applySuperResolutionEnabled(
  config: WorkflowConfig,
  value: boolean,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.enabled = value
  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function applyInterpolationBackendSelection(
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

export function applySuperResolutionBackendSelection(
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

export function applyInterpolationAlgorithmSelection(
  config: WorkflowConfig,
  value: string,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.interpolation.algorithm = value
  config.interpolation.model = pickDefaultInterpolationModel(checkResult, value)
}

export function applySuperResolutionAlgorithmSelection(
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

export function applySuperResolutionScale(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): void {
  const algorithm = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
  config.superResolution.scaleFactor = fixedSuperResolutionScaleFactor(algorithm) ?? value
}

export function applySuperResolutionNumFrames(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): void {
  const algorithm = findSuperResolutionAlgorithm(checkResult, config.superResolution.algorithm)
  config.superResolution.numFrames = fixedRuntimeFrameCount(algorithm) ?? value
}
