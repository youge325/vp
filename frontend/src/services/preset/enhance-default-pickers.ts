// pure: no Vue / no Pinia / no Tauri
// Environment-backed default picker helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'
import { findInterpolationAlgorithm, pickBackendSupportedAlgorithmName } from './enhance-workflow-lookup'

export function pickDefaultEngine(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine | undefined {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  return engines[0] as InferenceEngine | undefined
}

export function pickDefaultInterpolationEngine(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine | undefined {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  if (vendor === 'hygon') {
    return engines.includes('dcu') ? 'dcu' : (engines[0] as InferenceEngine | undefined)
  }
  if (vendor === 'nvidia') {
    return engines.includes('tensorrt') ? 'tensorrt' : (engines[0] as InferenceEngine | undefined)
  }
  return engines[0] as InferenceEngine | undefined
}

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(checkResult?.interpolationAlgorithms, backend, 'rife')
}

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return findInterpolationAlgorithm(checkResult, algorithm)?.models?.[0] ?? '4.25'
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(checkResult?.superResolutionAlgorithms, backend, 'placeholder')
}

export function pickDefaultAnimeProfile(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.animeProfiles?.[0] ?? 'clean-lines'
}
