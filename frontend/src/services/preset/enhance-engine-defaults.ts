// pure: no Vue / no Pinia / no Tauri
// Environment-backed engine default helpers for enhance workflow rules.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'

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
