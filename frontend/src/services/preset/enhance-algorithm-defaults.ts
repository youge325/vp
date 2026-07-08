// pure: no Vue / no Pinia / no Tauri
// Environment-backed algorithm default helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import { pickBackendSupportedAlgorithmName } from './enhance-workflow-lookup'

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(checkResult?.interpolationAlgorithms, backend, 'rife')
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(checkResult?.superResolutionAlgorithms, backend, 'placeholder')
}
