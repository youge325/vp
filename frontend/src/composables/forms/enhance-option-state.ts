import { computed, toRef } from 'vue'

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
} from '@/services/preset/enhance-options'
import type { createEnhanceOptionBindings } from '@/composables/forms/enhance-option-bindings'

type EnhanceOptionForm = Parameters<typeof createEnhanceOptionBindings>[0]

const INTERPOLATION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录'
const SUPER_RESOLUTION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录'

export function createEnhanceOptionState(form: EnhanceOptionForm) {
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

  return {
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
  }
}
