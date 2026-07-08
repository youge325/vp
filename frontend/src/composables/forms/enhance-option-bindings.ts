import { computed, reactive, toRef } from 'vue'

import { useGpuCapabilities } from '@/composables/selectors/useGpuCapabilities'
import {
  FPS_MODE_OPTIONS,
  MULTI_OPTIONS,
  PROCESS_ORDER_OPTIONS,
  buildAlgorithmOptions,
  buildBackendOptions,
  buildEngineOptions,
  buildModelOptions,
  buildOnnxModelOptions,
  buildProfileOptions,
  toFpsMode,
  toInferenceEngine,
  toNumberOption,
  toProcessOrder,
  toTensorBackend,
} from '@/services/preset/enhance-options'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'

export interface EnhanceOptionForm {
  interpolationBackend: TensorBackend
  interpolationEngine: InferenceEngine
  interpolationAlgorithm: string
  interpolationModel: string
  interpolationOnnxModel: string
  interpolationAlgorithms: AlgorithmInfo[]
  interpolationModels: string[]
  interpolationOnnxModels: string[]
  interpolationModelDetails: ModelVariantInfo[]
  interpolationOnnxModelDetails: ModelVariantInfo[]
  fpsMode: FpsMode
  interpolationMulti: number

  superResolutionBackend: TensorBackend
  superResolutionEngine: InferenceEngine
  superResolutionAlgorithm: string
  superResolutionOnnxModel: string
  superResolutionScale: number
  superResolutionAlgorithms: AlgorithmInfo[]
  superResolutionOnnxModels: string[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]

  processOrder: ProcessOrder
  animeProfile: string
  animeProfiles: string[]
}

const INTERPOLATION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录'
const SUPER_RESOLUTION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录'

export function createEnhanceOptionBindings(form: EnhanceOptionForm) {
  const interpolationCapabilities = useGpuCapabilities(toRef(form, 'interpolationBackend'))
  const superResolutionCapabilities = useGpuCapabilities(toRef(form, 'superResolutionBackend'))

  const backendOptions = computed(() =>
    buildBackendOptions(interpolationCapabilities.visibleBackends.value),
  )
  const interpolationEngineOptions = computed(() =>
    buildEngineOptions(interpolationCapabilities.availableEngines.value),
  )
  const superResolutionEngineOptions = computed(() =>
    buildEngineOptions(superResolutionCapabilities.availableEngines.value),
  )
  const interpolationAlgorithmOptions = computed(() =>
    buildAlgorithmOptions(form.interpolationAlgorithms, 'name'),
  )
  const interpolationModelOptions = computed(() =>
    buildModelOptions(form.interpolationModels, form.interpolationModelDetails),
  )
  const interpolationOnnxOptions = computed(() =>
    buildOnnxModelOptions(form.interpolationOnnxModels, form.interpolationOnnxModelDetails),
  )
  const interpolationOnnxDisabled = computed(() => form.interpolationOnnxModels.length === 0)
  const interpolationOnnxHint = computed(() =>
    interpolationOnnxDisabled.value ? INTERPOLATION_ONNX_EMPTY_HINT : undefined,
  )
  const superResolutionAlgorithmOptions = computed(() =>
    buildAlgorithmOptions(form.superResolutionAlgorithms, 'modelMetrics'),
  )
  const superResolutionOnnxOptions = computed(() =>
    buildOnnxModelOptions(form.superResolutionOnnxModels, form.superResolutionOnnxModelDetails),
  )
  const superResolutionOnnxDisabled = computed(() => form.superResolutionOnnxModels.length === 0)
  const superResolutionOnnxHint = computed(() =>
    superResolutionOnnxDisabled.value ? SUPER_RESOLUTION_ONNX_EMPTY_HINT : undefined,
  )
  const animeProfileOptions = computed(() => buildProfileOptions(form.animeProfiles))

  function setInterpolationBackend(value: string): void {
    form.interpolationBackend = toTensorBackend(value)
  }

  function setInterpolationEngine(value: string): void {
    form.interpolationEngine = toInferenceEngine(value)
  }

  function setInterpolationAlgorithm(value: string): void {
    form.interpolationAlgorithm = value
  }

  function setInterpolationModel(value: string): void {
    form.interpolationModel = value
  }

  function setInterpolationOnnxModel(value: string): void {
    form.interpolationOnnxModel = value
  }

  function setFpsMode(value: string): void {
    form.fpsMode = toFpsMode(value)
  }

  function setInterpolationMulti(value: string): void {
    form.interpolationMulti = toNumberOption(value)
  }

  function setSuperResolutionBackend(value: string): void {
    form.superResolutionBackend = toTensorBackend(value)
  }

  function setSuperResolutionEngine(value: string): void {
    form.superResolutionEngine = toInferenceEngine(value)
  }

  function setSuperResolutionAlgorithm(value: string): void {
    form.superResolutionAlgorithm = value
  }

  function setSuperResolutionOnnxModel(value: string): void {
    form.superResolutionOnnxModel = value
  }

  function setSuperResolutionScale(value: string): void {
    form.superResolutionScale = toNumberOption(value)
  }

  function setProcessOrder(value: string): void {
    form.processOrder = toProcessOrder(value)
  }

  function setAnimeProfile(value: string): void {
    form.animeProfile = value
  }

  return reactive({
    backendOptions,
    interpolationEngineOptions,
    superResolutionEngineOptions,
    interpolationAlgorithmOptions,
    interpolationModelOptions,
    interpolationOnnxOptions,
    interpolationOnnxDisabled,
    interpolationOnnxHint,
    superResolutionAlgorithmOptions,
    superResolutionOnnxOptions,
    superResolutionOnnxDisabled,
    superResolutionOnnxHint,
    animeProfileOptions,
    interpolationShowEngineSelector: interpolationCapabilities.showEngineSelector,
    superResolutionShowEngineSelector: superResolutionCapabilities.showEngineSelector,
    fpsModeOptions: FPS_MODE_OPTIONS,
    multiOptions: MULTI_OPTIONS,
    processOrderOptions: PROCESS_ORDER_OPTIONS,
    setInterpolationBackend,
    setInterpolationEngine,
    setInterpolationAlgorithm,
    setInterpolationModel,
    setInterpolationOnnxModel,
    setFpsMode,
    setInterpolationMulti,
    setSuperResolutionBackend,
    setSuperResolutionEngine,
    setSuperResolutionAlgorithm,
    setSuperResolutionOnnxModel,
    setSuperResolutionScale,
    setProcessOrder,
    setAnimeProfile,
  })
}
