// pure: no Vue / no Pinia / no Tauri
// Environment-backed default picker helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import { findInterpolationAlgorithm, pickBackendSupportedAlgorithmName } from './enhance-workflow-lookup'

export { pickDefaultEngine, pickDefaultInterpolationEngine } from './enhance-engine-defaults'

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
