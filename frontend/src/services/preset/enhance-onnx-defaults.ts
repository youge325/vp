// pure: no Vue / no Pinia / no Tauri
// ONNX model fallback helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'

import { findInterpolationAlgorithm, findSuperResolutionAlgorithm } from './enhance-workflow-lookup'

export function fallbackInterpolationOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  return findInterpolationAlgorithm(checkResult, algorithm)?.onnxModels?.[0] || ''
}

export function fallbackSuperResolutionOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  return findSuperResolutionAlgorithm(checkResult, algorithm)?.onnxModels?.[0] || ''
}
