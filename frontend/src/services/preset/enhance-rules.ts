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
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  const alg = checkResult?.interpolationAlgorithms?.find((a) => a.name === algorithm)
  return alg?.onnxModels?.[0] || ''
}

export function fallbackSuperResolutionOnnxModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
  current: string | undefined,
): string {
  if (current) return current
  const alg = checkResult?.superResolutionAlgorithms?.find((a) => a.name === algorithm)
  return alg?.onnxModels?.[0] || ''
}

export function pickDefaultInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.interpolationAlgorithms?.[0]?.name ?? 'rife'
}

export function pickDefaultInterpolationModel(
  checkResult: EnvironmentCheckResult | null,
  algorithm: string,
): string {
  return (
    checkResult?.interpolationAlgorithms?.find((a) => a.name === algorithm)?.models?.[0] ??
    '4.25'
  )
}

export function pickDefaultSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.superResolutionAlgorithms?.[0]?.name ?? 'placeholder'
}

export function pickDefaultAnimeProfile(
  checkResult: EnvironmentCheckResult | null,
): string {
  return checkResult?.animeProfiles?.[0] ?? 'clean-lines'
}
