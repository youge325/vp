// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 把 EnhanceModuleView 的 18 个双向 computed 折叠到此处,业务规则在 services/preset/enhance-rules。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  pickDefaultEngine,
} from '@/services/preset/enhance-rules'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const { editorConfig } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)

  const interpolationOnnxModels = computed(
    () => envStore.env.checkResult?.onnxModels?.interpolation ?? [],
  )
  const superResolutionOnnxModels = computed(
    () => envStore.env.checkResult?.onnxModels?.super_resolution ?? [],
  )
  const isOnnxBackend = computed(() => workflow.value.interpolation.tensorBackend === 'onnx')

  const interpolationEnabled = computed({
    get: () => workflow.value.interpolation.enabled,
    set: (value: boolean) => presetStore.patchWorkflow((c) => { c.interpolation.enabled = value }),
  })

  const interpolationBackend = computed({
    get: () => workflow.value.interpolation.tensorBackend as TensorBackend,
    set: (value: TensorBackend) => {
      presetStore.patchWorkflow((c) => {
        c.interpolation.tensorBackend = value
        c.interpolation.engine = pickDefaultEngine(envStore.env.checkResult, value) ?? c.interpolation.engine
        if (value === 'onnx') {
          c.interpolation.onnxModel = fallbackInterpolationOnnxModel(envStore.env.checkResult, c.interpolation.onnxModel)
          c.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(envStore.env.checkResult, c.superResolution.onnxModel)
        }
      })
    },
  })

  const interpolationEngine = computed({
    get: () => (workflow.value.interpolation.engine as InferenceEngine) ?? 'cuda',
    set: (value: InferenceEngine) => presetStore.patchWorkflow((c) => { c.interpolation.engine = value }),
  })

  const interpolationModel = computed({
    get: () => workflow.value.interpolation.model,
    set: (value: string) => presetStore.patchWorkflow((c) => { c.interpolation.model = value }),
  })

  const interpolationOnnxModel = computed({
    get: () => workflow.value.interpolation.onnxModel ?? '',
    set: (value: string) => presetStore.patchWorkflow((c) => { c.interpolation.onnxModel = value }),
  })

  const fpsMode = computed({
    get: () => workflow.value.fpsMode as FpsMode,
    set: (value: FpsMode) => presetStore.patchWorkflow((c) => { c.fpsMode = value }),
  })

  const targetFps = computed({
    get: () => workflow.value.interpolation.targetFps,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.interpolation.targetFps = value }),
  })

  const interpolationMulti = computed({
    get: () => workflow.value.interpolation.multi,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.interpolation.multi = value }),
  })

  const interpolationScale = computed({
    get: () => workflow.value.interpolation.scale,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.interpolation.scale = value }),
  })

  const interpolationFp16 = computed({
    get: () => workflow.value.interpolation.fp16,
    set: (value: boolean) => presetStore.patchWorkflow((c) => { c.interpolation.fp16 = value }),
  })

  const superResolutionEnabled = computed({
    get: () => workflow.value.superResolution.enabled,
    set: (value: boolean) => presetStore.patchWorkflow((c) => { c.superResolution.enabled = value }),
  })

  const superResolutionScale = computed({
    get: () => workflow.value.superResolution.scaleFactor,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.superResolution.scaleFactor = value }),
  })

  const superResolutionAlgorithm = computed({
    get: () => workflow.value.superResolution.algorithm,
    set: (value: string) => presetStore.patchWorkflow((c) => { c.superResolution.algorithm = value }),
  })

  const superResolutionOnnxModel = computed({
    get: () => workflow.value.superResolution.onnxModel ?? '',
    set: (value: string) => presetStore.patchWorkflow((c) => { c.superResolution.onnxModel = value }),
  })

  const processOrder = computed({
    get: () => workflow.value.processOrder as ProcessOrder,
    set: (value: ProcessOrder) => presetStore.patchWorkflow((c) => { c.processOrder = value }),
  })

  const animeEnabled = computed({
    get: () => workflow.value.anime.enabled,
    set: (value: boolean) => presetStore.patchWorkflow((c) => { c.anime.enabled = value }),
  })

  const animeProfile = computed({
    get: () => workflow.value.anime.profile,
    set: (value: string) => presetStore.patchWorkflow((c) => { c.anime.profile = value }),
  })

  const animeDenoise = computed({
    get: () => workflow.value.anime.denoise,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.anime.denoise = value }),
  })

  const animeEdgeBoost = computed({
    get: () => workflow.value.anime.edgeBoost,
    set: (value: number) => presetStore.patchWorkflow((c) => { c.anime.edgeBoost = value }),
  })

  return reactive({
    interpolationOnnxModels,
    superResolutionOnnxModels,
    isOnnxBackend,
    interpolationEnabled,
    interpolationBackend,
    interpolationEngine,
    interpolationModel,
    interpolationOnnxModel,
    fpsMode,
    targetFps,
    interpolationMulti,
    interpolationScale,
    interpolationFp16,
    superResolutionEnabled,
    superResolutionScale,
    superResolutionAlgorithm,
    superResolutionOnnxModel,
    processOrder,
    animeEnabled,
    animeProfile,
    animeDenoise,
    animeEdgeBoost,
  })
}
