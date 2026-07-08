// pure: no Vue / no Pinia / no Tauri
// 增强模块规则 — 切换后端时自动选择推理引擎与 ONNX 模型兜底。

import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

// Phase 8 — every "pick default *" helper now requires the
// ``backend`` argument so it can filter the candidate list against
// ``alg.tensorBackends.includes(backend)``. Without this, callers
// would always pick the first algorithm registered (RIFE), which is
// wrong when the user is on Paddle and RIFE has no Paddle impl.
// The legacy "pick first" fallback only fires when **no** algorithm
// declares support for the requested backend.

function backendCompatible(
  alg: { tensorBackends?: ReadonlyArray<string> } | null | undefined,
  backend: TensorBackend,
): boolean {
  return Boolean(alg?.tensorBackends?.includes(backend))
}

export function isPaddleGanVsrAlgorithm(algorithm: AlgorithmInfo | null | undefined): boolean {
  if (!algorithm) return false
  if (algorithm.family === 'paddlegan_vsr') return true
  return (
    algorithm.tensorBackends?.includes('paddle') &&
    (algorithm.sequenceMode === 'recurrent' || algorithm.sequenceMode === 'window') &&
    algorithm.scaleFactors?.length === 1 &&
    algorithm.scaleFactors[0] === 4
  )
}

export function superResolutionInputFrameMode(
  algorithm: AlgorithmInfo | null | undefined,
): NonNullable<AlgorithmInfo['inputFrameMode']> {
  if (algorithm?.inputFrameMode) return algorithm.inputFrameMode
  if (!isPaddleGanVsrAlgorithm(algorithm)) return 'none'
  return algorithm?.sequenceMode === 'window' ? 'fixed_window' : 'editable_chunk'
}

export function fixedRuntimeFrameCount(algorithm: AlgorithmInfo | null | undefined): number | null {
  if (superResolutionInputFrameMode(algorithm) !== 'fixed_window') return null
  const count = algorithm?.modelDetails?.[0]?.metrics.runtimeFrameCount ?? algorithm?.defaultNumFrames ?? null
  return typeof count === 'number' && Number.isFinite(count) ? Math.max(1, Math.round(count)) : null
}

export function fixedSuperResolutionScaleFactor(algorithm: AlgorithmInfo | null | undefined): number | null {
  if (!isPaddleGanVsrAlgorithm(algorithm)) return null
  const explicit = algorithm?.fixedScaleFactor
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit
  }
  const scale = algorithm?.scaleFactors?.length === 1 ? algorithm.scaleFactors[0] : null
  return typeof scale === 'number' && Number.isFinite(scale) ? scale : null
}

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

export function pickDefaultEngine(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine | undefined {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  return engines[0] as InferenceEngine | undefined
}

export function fallbackInterpolationOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  const alg = checkResult?.interpolationAlgorithms?.find((a) => a.name === algorithm)
  return alg?.onnxModels?.[0] || ''
}

export function fallbackSuperResolutionOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  const alg = checkResult?.superResolutionAlgorithms?.find((a) => a.name === algorithm)
  return alg?.onnxModels?.[0] || ''
}

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  const all = checkResult?.interpolationAlgorithms ?? []
  return all.find((a) => backendCompatible(a, backend))?.name ?? all[0]?.name ?? 'rife'
}

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return (
    checkResult?.interpolationAlgorithms?.find((a) => a.name === algorithm)?.models?.[0] ??
    '4.25'
  )
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  const all = checkResult?.superResolutionAlgorithms ?? []
  return all.find((a) => backendCompatible(a, backend))?.name ?? all[0]?.name ?? 'placeholder'
}

export function pickDefaultAnimeProfile(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.animeProfiles?.[0] ?? 'clean-lines'
}
