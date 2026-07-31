// pure: no Vue / no Pinia / no Tauri
// GPU 能力投影 — tensorEngines 是 backend / engine 可见性的唯一事实来源。

import type { EnvironmentCheckResult, InferenceEngine, TensorBackend } from '@/types/protocol'

const ALL_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']
type TensorEngineSnapshot = Pick<EnvironmentCheckResult, 'tensorEngines'>

export function getVisibleBackends(
  checkResult: TensorEngineSnapshot | null,
): TensorBackend[] {
  if (!checkResult) return [...ALL_BACKENDS]

  return ALL_BACKENDS.filter((backend) => checkResult.tensorEngines[backend].length > 0)
}

export function getAvailableEngines(
  checkResult: TensorEngineSnapshot | null,
  backend: TensorBackend,
): InferenceEngine[] {
  return checkResult?.tensorEngines[backend] ?? []
}

export function shouldShowEngineSelector(
  checkResult: TensorEngineSnapshot | null,
  backend: TensorBackend,
): boolean {
  return getAvailableEngines(checkResult, backend).length > 0
}
