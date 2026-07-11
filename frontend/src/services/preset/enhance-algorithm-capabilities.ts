// pure: no Vue / no Pinia / no Tauri
// Algorithm capability metadata helpers for enhance rules.

import type { AlgorithmInfo } from '@/types/protocol'

export function isPaddleGanVsrAlgorithm(algorithm: AlgorithmInfo | null | undefined): boolean {
  return algorithm?.family === 'paddlegan_vsr'
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

export function fixedSuperResolutionScaleFactor(algorithm: AlgorithmInfo | null | undefined): number | null {
  if (!isPaddleGanVsrAlgorithm(algorithm)) return null
  const explicit = algorithm?.fixedScaleFactor
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit
  }
  const scale = algorithm?.scaleFactors?.length === 1 ? algorithm.scaleFactors[0] : null
  return typeof scale === 'number' && Number.isFinite(scale) ? scale : null
}
