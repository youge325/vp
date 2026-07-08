// pure: no Vue / no Pinia / no Tauri
// Environment-backed model/profile default helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import { findInterpolationAlgorithm } from './enhance-workflow-lookup'

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return findInterpolationAlgorithm(checkResult, algorithm)?.models?.[0] ?? '4.25'
}

export function pickDefaultAnimeProfile(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.animeProfiles?.[0] ?? 'clean-lines'
}
