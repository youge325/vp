// pure: no Vue / no Pinia / no Tauri
// Select option rules for the enhance view.

import { modelOptionLabel } from '@/services/model-metric-format'
import {
  getAvailableEngines,
  getVisibleBackends,
  shouldShowEngineSelector,
} from '@/services/env/gpu-capabilities'
import type {
  AlgorithmInfo,
  EnvironmentCheckResult,
  FpsMode,
  InferenceEngine,
  ModelVariantInfo,
  ProcessOrder,
  TensorBackend,
} from '@/types/protocol'
import type { SelectOption } from '@/types/view/select-option'

const BACKEND_LABELS: Record<TensorBackend, string> = {
  pytorch: 'PyTorch',
  paddle: 'PaddlePaddle',
  onnx: 'ONNX Runtime',
}

const ENGINE_LABELS: Record<InferenceEngine, string> = {
  cuda: 'CUDA',
  tensorrt: 'TensorRT',
  dcu: 'DCU',
}

const FPS_MODE_OPTIONS: readonly SelectOption<FpsMode>[] = [
  { value: 'target', label: '目标 FPS' },
  { value: 'multi', label: '倍率' },
] as const

const MULTI_OPTIONS: readonly SelectOption[] = [
  { value: '2', label: '2x' },
  { value: '4', label: '4x' },
] as const

const PROCESS_ORDER_OPTIONS: readonly SelectOption<ProcessOrder>[] = [
  { value: 'super_resolution_then_interpolation', label: '先超分后补帧' },
  { value: 'frame_interpolation_then_super_resolution', label: '先补帧后超分' },
] as const

const INTERPOLATION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录'
const SUPER_RESOLUTION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录'

interface EnhanceOptionInput {
  checkResult: Pick<EnvironmentCheckResult, 'tensorEngines'> | null
  interpolationBackend: TensorBackend
  superResolutionBackend: TensorBackend
  interpolationAlgorithms: readonly AlgorithmInfo[]
  interpolationModels: readonly string[]
  interpolationOnnxModels: readonly string[]
  interpolationModelDetails: readonly ModelVariantInfo[]
  interpolationOnnxModelDetails: readonly ModelVariantInfo[]
  superResolutionAlgorithms: readonly AlgorithmInfo[]
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
  superResolutionScaleFactor: number
  superResolutionOnnxModels: readonly string[]
  superResolutionOnnxModelDetails: readonly ModelVariantInfo[]
}

export interface EnhanceOptions {
  backendOptions: SelectOption<TensorBackend>[]
  interpolationEngineOptions: SelectOption<InferenceEngine>[]
  superResolutionEngineOptions: SelectOption<InferenceEngine>[]
  interpolationAlgorithmOptions: SelectOption[]
  interpolationModelOptions: SelectOption[]
  interpolationOnnxOptions: SelectOption[]
  interpolationOnnxDisabled: boolean
  interpolationOnnxHint: string | undefined
  superResolutionAlgorithmOptions: SelectOption[]
  superResolutionScaleOptions: SelectOption[]
  superResolutionOnnxOptions: SelectOption[]
  superResolutionOnnxDisabled: boolean
  superResolutionOnnxHint: string | undefined
  interpolationShowEngineSelector: boolean
  superResolutionShowEngineSelector: boolean
  fpsModeOptions: readonly SelectOption<FpsMode>[]
  multiOptions: readonly SelectOption[]
  processOrderOptions: readonly SelectOption<ProcessOrder>[]
}

function findDetail(details: readonly ModelVariantInfo[], name: string): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === name)
}

function buildBackendOptions(backends: readonly TensorBackend[]): SelectOption<TensorBackend>[] {
  return backends.map((value) => ({ value, label: BACKEND_LABELS[value] }))
}

function buildEngineOptions(engines: readonly InferenceEngine[]): SelectOption<InferenceEngine>[] {
  return engines.map((value) => ({ value, label: ENGINE_LABELS[value] }))
}

function buildModelOptions(
  models: readonly string[],
  details: readonly ModelVariantInfo[],
): SelectOption[] {
  return models.map((model) => ({
    value: model,
    label: modelOptionLabel(model, findDetail(details, model)),
  }))
}

function buildOnnxModelOptions(
  models: readonly string[],
  details: readonly ModelVariantInfo[],
): SelectOption[] {
  return [
    { value: '', label: '未选择' },
    ...buildModelOptions(models, details),
  ]
}

function buildAlgorithmOptions(
  algorithms: readonly AlgorithmInfo[],
  labelMode: 'name' | 'modelMetrics',
  selectedModelName?: string,
): SelectOption[] {
  return algorithms.map((algorithm) => ({
    value: algorithm.name,
    label: labelMode === 'modelMetrics'
      ? modelOptionLabel(
          algorithm.name,
          selectedModelName
            ? findDetail(algorithm.modelDetails ?? [], selectedModelName) ?? algorithm.modelDetails?.[0]
            : algorithm.modelDetails?.[0],
        )
      : algorithm.name,
  }))
}

export function buildEnhanceOptions({
  checkResult,
  interpolationBackend,
  superResolutionBackend,
  interpolationAlgorithms,
  interpolationModels,
  interpolationOnnxModels,
  interpolationModelDetails,
  interpolationOnnxModelDetails,
  superResolutionAlgorithms,
  currentSuperResolutionAlgorithm,
  superResolutionScaleFactor,
  superResolutionOnnxModels,
  superResolutionOnnxModelDetails,
}: EnhanceOptionInput): EnhanceOptions {
  const interpolationOnnxDisabled = interpolationOnnxModels.length === 0
  const superResolutionOnnxDisabled = superResolutionOnnxModels.length === 0

  return {
    backendOptions: buildBackendOptions(getVisibleBackends(checkResult)),
    interpolationEngineOptions: buildEngineOptions(
      getAvailableEngines(checkResult, interpolationBackend),
    ),
    superResolutionEngineOptions: buildEngineOptions(
      getAvailableEngines(checkResult, superResolutionBackend),
    ),
    interpolationAlgorithmOptions: buildAlgorithmOptions(interpolationAlgorithms, 'name'),
    interpolationModelOptions: buildModelOptions(interpolationModels, interpolationModelDetails),
    interpolationOnnxOptions: buildOnnxModelOptions(
      interpolationOnnxModels,
      interpolationOnnxModelDetails,
    ),
    interpolationOnnxDisabled,
    interpolationOnnxHint: interpolationOnnxDisabled ? INTERPOLATION_ONNX_EMPTY_HINT : undefined,
    superResolutionAlgorithmOptions: buildAlgorithmOptions(
      superResolutionAlgorithms,
      'modelMetrics',
      `x${superResolutionScaleFactor}`,
    ),
    superResolutionScaleOptions: (
      currentSuperResolutionAlgorithm?.scaleFactors.length
        ? currentSuperResolutionAlgorithm.scaleFactors
        : MULTI_OPTIONS.map((option) => Number(option.value))
    ).map((value) => ({ value: String(value), label: `${value}x` })),
    superResolutionOnnxOptions: buildOnnxModelOptions(
      superResolutionOnnxModels,
      superResolutionOnnxModelDetails,
    ),
    superResolutionOnnxDisabled,
    superResolutionOnnxHint: superResolutionOnnxDisabled
      ? SUPER_RESOLUTION_ONNX_EMPTY_HINT
      : undefined,
    interpolationShowEngineSelector: shouldShowEngineSelector(checkResult, interpolationBackend),
    superResolutionShowEngineSelector: shouldShowEngineSelector(
      checkResult,
      superResolutionBackend,
    ),
    fpsModeOptions: FPS_MODE_OPTIONS,
    multiOptions: MULTI_OPTIONS,
    processOrderOptions: PROCESS_ORDER_OPTIONS,
  }
}
