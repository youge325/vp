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

export const RIFE_MODELS = [
  '4.0',
  '4.1',
  '4.2',
  '4.3',
  '4.4',
  '4.5',
  '4.6',
  '4.7',
  '4.8',
  '4.9',
  '4.10',
  '4.11',
  '4.12',
  '4.12.lite',
  '4.13',
  '4.13.lite',
  '4.14',
  '4.14.lite',
  '4.15',
  '4.15.lite',
  '4.16.lite',
  '4.17',
  '4.17.lite',
  '4.18',
  '4.19',
  '4.20',
  '4.21',
  '4.22',
  '4.22.lite',
  '4.23',
  '4.24',
  '4.25',
  '4.25.lite',
  '4.25.heavy',
  '4.26',
  '4.26.heavy',
]
