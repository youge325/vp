// pure: no Vue / no Pinia / no Tauri
// Environment-backed default picker helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'
import { algorithmSupportsBackend } from './enhance-workflow-lookup'

export function pickDefaultEngine(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine | undefined {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  return engines[0] as InferenceEngine | undefined
}

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  const all = checkResult?.interpolationAlgorithms ?? []
  return all.find((a) => algorithmSupportsBackend(a, backend))?.name ?? all[0]?.name ?? 'rife'
}

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return checkResult?.interpolationAlgorithms?.find((a) => a.name === algorithm)?.models?.[0] ?? '4.25'
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  const all = checkResult?.superResolutionAlgorithms ?? []
  return all.find((a) => algorithmSupportsBackend(a, backend))?.name ?? all[0]?.name ?? 'placeholder'
}

export function pickDefaultAnimeProfile(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.animeProfiles?.[0] ?? 'clean-lines'
}
