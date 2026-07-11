// pure: no Vue / no Pinia / no Tauri
// Environment-backed model/profile default helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/protocol'
import { findInterpolationAlgorithm } from './enhance-workflow-lookup'

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return findInterpolationAlgorithm(checkResult, algorithm)?.models?.[0] ?? '4.25'
}
