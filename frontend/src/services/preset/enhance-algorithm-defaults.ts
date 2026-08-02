// pure: no Vue / no Pinia / no Tauri
// Environment-backed algorithm default helpers for enhance workflow rules.

import { APPLICATION_DEFAULTS } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { TensorBackend } from '@/types/protocol'
import { pickBackendSupportedAlgorithmName } from './enhance-workflow-lookup'

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(
    checkResult?.interpolationAlgorithms,
    backend,
    APPLICATION_DEFAULTS.interpolation.algorithm,
  )
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): string {
  return pickBackendSupportedAlgorithmName(
    checkResult?.superResolutionAlgorithms,
    backend,
    APPLICATION_DEFAULTS.superResolution.algorithm,
  )
}
