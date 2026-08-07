// pure: no Vue / no Pinia / no Tauri
// Algorithm capability metadata helpers for enhance rules.

import type { AlgorithmInfo } from '@/types/protocol'

export function isPaddleGanVsrAlgorithm(algorithm: AlgorithmInfo | null | undefined): boolean {
  return algorithm?.family === 'paddlegan_vsr'
}

export function isPytorchVsrAlgorithm(algorithm: AlgorithmInfo | null | undefined): boolean {
  return algorithm?.family === 'pytorch_vsr'
}

export function superResolutionInputFrameMode(
  algorithm: AlgorithmInfo | null | undefined,
): AlgorithmInfo['inputFrameMode'] {
  return algorithm?.inputFrameMode ?? 'none'
}

export function fixedRuntimeFrameCount(algorithm: AlgorithmInfo | null | undefined): number | null {
  if (superResolutionInputFrameMode(algorithm) !== 'fixed_window') return null
  const count = algorithm?.modelDetails?.[0]?.metrics.runtimeFrameCount ?? algorithm?.defaultNumFrames ?? null
  return typeof count === 'number' && Number.isFinite(count) ? Math.max(1, Math.round(count)) : null
}

export function superResolutionScaleFactors(
  algorithm: AlgorithmInfo | null | undefined,
): readonly number[] {
  return algorithm?.scaleFactors?.filter(
    (value) => typeof value === 'number' && Number.isFinite(value) && value > 0,
  ) ?? []
}
