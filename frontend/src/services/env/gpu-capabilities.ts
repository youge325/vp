// pure: no Vue / no Pinia / no Tauri
// GPU 能力投影 — tensorEngines 是 backend / engine 可见性的唯一事实来源。

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'

const ALL_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

export function getVisibleBackends(
  checkResult: EnvironmentCheckResult | null,
): TensorBackend[] {
  if (!checkResult) return [...ALL_BACKENDS]

  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  const support = checkResult.backendDeviceSupport
  const available = ALL_BACKENDS.filter((backend) => checkResult.tensorEngines[backend].length > 0)

  if (!vendor || vendor === 'other') return available
  return available.filter((b) => {
    const supported = support[b]
    return supported.length > 0 && supported.includes(vendor)
  })
}

export function getAvailableEngines(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine[] {
  return (checkResult?.tensorEngines[backend] ?? []) as InferenceEngine[]
}

export function shouldShowEngineSelector(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): boolean {
  return getAvailableEngines(checkResult, backend).length > 0
}
