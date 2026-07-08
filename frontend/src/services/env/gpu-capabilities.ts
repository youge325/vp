// pure: no Vue / no Pinia / no Tauri
// GPU 能力推断 — 从环境探测结果推断可用 backend / engine。

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'

const ALL_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

export function getVisibleBackends(
  checkResult: EnvironmentCheckResult | null,
): TensorBackend[] {
  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  const support = checkResult?.backendDeviceSupport

  if (!vendor || vendor === 'other' || !support) {
    return [...ALL_BACKENDS]
  }

  const filtered = ALL_BACKENDS.filter((b) => {
    const supported = support[b]
    return supported && supported.length > 0 ? supported.includes(vendor) : true
  })

  if (filtered.length > 0) {
    return filtered
  }

  if (vendor === 'hygon') {
    return ['paddle']
  }

  return [...ALL_BACKENDS]
}

export function getAvailableEngines(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine[] {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  if (engines.length > 0) {
    return engines as InferenceEngine[]
  }

  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  const cudaAvailable = checkResult?.gpu?.cudaAvailable
  const gpuAvailable = checkResult?.gpu?.available
  const deviceNames = checkResult?.gpu?.devices ?? []
  const hasNvidiaInName = deviceNames.some((name) => name.toLowerCase().includes('nvidia'))
  const isNvidia = vendor === 'nvidia' || cudaAvailable || hasNvidiaInName || (gpuAvailable === true && vendor === undefined)

  if (isNvidia) {
    if (backend === 'pytorch') return ['cuda', 'tensorrt']
    if (backend === 'paddle') return ['cuda', 'tensorrt']
    if (backend === 'onnx') return ['tensorrt', 'cuda']
  }

  if (vendor === 'hygon' && backend === 'paddle') return ['dcu']
  if (vendor === 'hygon') return []

  return ['cuda']
}

export function shouldShowEngineSelector(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): boolean {
  const gpuAvailable = checkResult?.gpu?.available
  return gpuAvailable === true && getAvailableEngines(checkResult, backend).length > 0
}
