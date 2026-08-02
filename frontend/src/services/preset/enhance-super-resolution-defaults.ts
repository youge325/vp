// pure: no Vue / no Pinia / no Tauri
// Super-resolution workflow mutation defaults for selected algorithms.

import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import {
  fixedRuntimeFrameCount,
  isPytorchVsrAlgorithm,
  isPaddleGanVsrAlgorithm,
  superResolutionScaleFactors,
} from './enhance-algorithm-capabilities'
import { fallbackSuperResolutionOnnxModel } from './enhance-onnx-defaults'

export function applySuperResolutionAlgorithmDefaults(
  config: WorkflowConfig,
  algorithm: AlgorithmInfo | null | undefined,
  checkResult: EnvironmentCheckResult | null,
): void {
  if (!algorithm) return

  if (isPaddleGanVsrAlgorithm(algorithm)) {
    config.superResolution.tensorBackend = 'paddle'
  } else if (isPytorchVsrAlgorithm(algorithm)) {
    config.superResolution.tensorBackend = 'pytorch'
    config.superResolution.engine = 'cuda'
  }

  const scaleFactors = superResolutionScaleFactors(algorithm)
  if (scaleFactors.length > 0 && !scaleFactors.includes(config.superResolution.scaleFactor)) {
    config.superResolution.scaleFactor = scaleFactors[0] ?? config.superResolution.scaleFactor
  }

  if (isPaddleGanVsrAlgorithm(algorithm) || isPytorchVsrAlgorithm(algorithm)) {
    config.superResolution.onnxModel = ''
    config.superResolution.numFrames =
      fixedRuntimeFrameCount(algorithm) ??
      algorithm.defaultNumFrames ??
      config.superResolution.numFrames ??
      10
    return
  }

  if (config.superResolution.tensorBackend === 'onnx') {
    config.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
      checkResult,
      config.superResolution.algorithm,
      config.superResolution.onnxModel,
    )
  }
}
