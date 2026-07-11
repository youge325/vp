import { computed } from 'vue'

import {
  getAvailableEngines,
  getVisibleBackends,
  shouldShowEngineSelector,
} from '@/services/env/gpu-capabilities'
import {
  FPS_MODE_OPTIONS,
  MULTI_OPTIONS,
  PROCESS_ORDER_OPTIONS,
  buildAlgorithmOptions,
  buildBackendOptions,
  buildEngineOptions,
  buildModelOptions,
  buildOnnxModelOptions,
} from '@/services/preset/enhance-options'
import type { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEnvStore } from '@/stores/env'

type EnhanceOptionFormField =
  | 'interpolationBackend'
  | 'interpolationEngine'
  | 'interpolationAlgorithm'
  | 'interpolationModel'
  | 'interpolationOnnxModel'
  | 'interpolationAlgorithms'
  | 'interpolationModels'
  | 'interpolationOnnxModels'
  | 'interpolationModelDetails'
  | 'interpolationOnnxModelDetails'
  | 'fpsMode'
  | 'interpolationMulti'
  | 'superResolutionBackend'
  | 'superResolutionEngine'
  | 'superResolutionAlgorithm'
  | 'superResolutionOnnxModel'
  | 'superResolutionScale'
  | 'superResolutionAlgorithms'
  | 'superResolutionOnnxModels'
  | 'superResolutionOnnxModelDetails'
  | 'processOrder'

export type EnhanceOptionForm = Pick<ReturnType<typeof useEnhanceForm>, EnhanceOptionFormField>

const INTERPOLATION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录'
const SUPER_RESOLUTION_ONNX_EMPTY_HINT = '未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录'

export function createEnhanceOptionState(form: EnhanceOptionForm) {
  const envStore = useEnvStore()
  const visibleBackends = computed(() => getVisibleBackends(envStore.env.checkResult))
  const interpolationEngines = computed(() =>
    getAvailableEngines(envStore.env.checkResult, form.interpolationBackend),
  )
  const superResolutionEngines = computed(() =>
    getAvailableEngines(envStore.env.checkResult, form.superResolutionBackend),
  )

  const backendOptions = computed(() =>
    buildBackendOptions(visibleBackends.value),
  )
  const interpolationEngineOptions = computed(() =>
    buildEngineOptions(interpolationEngines.value),
  )
  const superResolutionEngineOptions = computed(() =>
    buildEngineOptions(superResolutionEngines.value),
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
    interpolationShowEngineSelector: computed(() =>
      shouldShowEngineSelector(envStore.env.checkResult, form.interpolationBackend),
    ),
    superResolutionShowEngineSelector: computed(() =>
      shouldShowEngineSelector(envStore.env.checkResult, form.superResolutionBackend),
    ),
    fpsModeOptions: FPS_MODE_OPTIONS,
    multiOptions: MULTI_OPTIONS,
    processOrderOptions: PROCESS_ORDER_OPTIONS,
  }
}
