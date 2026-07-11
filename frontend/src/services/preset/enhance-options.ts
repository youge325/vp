// pure: no Vue / no Pinia / no Tauri
// Select option and value conversion rules for the enhance view.

import { BACKEND_LABELS, ENGINE_LABELS } from '@/config/gpu-labels'
import { modelOptionLabel } from '@/services/model-metric-format'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { SelectOption } from '@/types/view/select-option'

export const FPS_MODE_OPTIONS: readonly SelectOption[] = [
  { value: 'target', label: '目标 FPS' },
  { value: 'multi', label: '倍率' },
] as const

export const MULTI_OPTIONS: readonly SelectOption[] = [
  { value: '2', label: '2x' },
  { value: '4', label: '4x' },
] as const

export const PROCESS_ORDER_OPTIONS: readonly SelectOption[] = [
  { value: 'super_resolution_then_interpolation', label: '先超分后补帧' },
  { value: 'frame_interpolation_then_super_resolution', label: '先补帧后超分' },
] as const

function findDetail(details: readonly ModelVariantInfo[], name: string): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === name)
}

export function buildBackendOptions(backends: readonly TensorBackend[]): SelectOption[] {
  return backends.map((value) => ({ value, label: BACKEND_LABELS[value] }))
}

export function buildEngineOptions(engines: readonly string[]): SelectOption[] {
  return engines.map((value) => ({ value, label: ENGINE_LABELS[value] || value }))
}

export function buildModelOptions(
  models: readonly string[],
  details: readonly ModelVariantInfo[],
): SelectOption[] {
  return models.map((model) => ({
    value: model,
    label: modelOptionLabel(model, findDetail(details, model)),
  }))
}

export function buildOnnxModelOptions(
  models: readonly string[],
  details: readonly ModelVariantInfo[],
): SelectOption[] {
  return [
    { value: '', label: '未选择' },
    ...buildModelOptions(models, details),
  ]
}

export function buildAlgorithmOptions(
  algorithms: readonly AlgorithmInfo[],
  labelMode: 'name' | 'modelMetrics',
): SelectOption[] {
  return algorithms.map((algorithm) => ({
    value: algorithm.name,
    label: labelMode === 'modelMetrics'
      ? modelOptionLabel(algorithm.name, algorithm.modelDetails?.[0])
      : algorithm.name,
  }))
}

export function toTensorBackend(value: string): TensorBackend {
  return value as TensorBackend
}

export function toInferenceEngine(value: string): InferenceEngine {
  return value as InferenceEngine
}

export function toFpsMode(value: string): FpsMode {
  return value as FpsMode
}

export function toProcessOrder(value: string): ProcessOrder {
  return value as ProcessOrder
}
