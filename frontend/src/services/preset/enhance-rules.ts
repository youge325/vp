// pure: no Vue / no Pinia / no Tauri
// 增强模块规则 — 切换后端时自动选择推理引擎与 ONNX 模型兜底。

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'

export function pickDefaultEngine(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine | undefined {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  return engines[0] as InferenceEngine | undefined
}

export function fallbackInterpolationOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  current: string | undefined,
): string {
  return current || checkResult?.onnxModels?.interpolation?.[0] || ''
}

export function fallbackSuperResolutionOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  current: string | undefined,
): string {
  return current || checkResult?.onnxModels?.super_resolution?.[0] || ''
}
