// pure: no Vue / no Pinia / no Tauri
// Super-resolution workflow mutation defaults for selected algorithms.

import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import {
  fixedRuntimeFrameCount,
  fixedSuperResolutionScaleFactor,
  isPaddleGanVsrAlgorithm,
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
    config.superResolution.scaleFactor =
      fixedSuperResolutionScaleFactor(algorithm) ?? config.superResolution.scaleFactor
    config.superResolution.onnxModel = ''
    config.superResolution.numFrames =
      fixedRuntimeFrameCount(algorithm) ??
      algorithm.defaultNumFrames ??
      config.superResolution.numFrames ??
      10
    return
  }

  if (
    algorithm.scaleFactors?.length &&
    !algorithm.scaleFactors.includes(config.superResolution.scaleFactor)
  ) {
    config.superResolution.scaleFactor = algorithm.scaleFactors[0] ?? config.superResolution.scaleFactor
  }

  if (config.superResolution.tensorBackend === 'onnx') {
    config.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
      checkResult,
      config.superResolution.algorithm,
      config.superResolution.onnxModel,
    )
  }
}
