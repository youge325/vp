// pure: no Vue / no Pinia / no Tauri
// ONNX model fallback helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'

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
