// pure: no Vue / no Pinia / no Tauri
// Select option rules for the enhance view.

import { modelOptionLabel } from '@/services/model-metric-format'
import type { AlgorithmInfo, ModelVariantInfo, TensorBackend } from '@/types/protocol'
import type { SelectOption } from '@/types/view/select-option'

const BACKEND_LABELS: Record<string, string> = {
  pytorch: 'PyTorch',
  paddle: 'PaddlePaddle',
  onnx: 'ONNX Runtime',
}

const ENGINE_LABELS: Record<string, string> = {
  cuda: 'CUDA',
  tensorrt: 'TensorRT',
  dcu: 'DCU',
  directml: 'DirectML',
  rocm: 'ROCm',
  cpu: 'CPU',
}

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
