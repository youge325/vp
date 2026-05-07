// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 把 EnhanceModuleView 的 18 个双向 computed 折叠到此处,业务规则在 services/preset/enhance-rules。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  pickDefaultEngine,
  pickDefaultInterpolationModel,
} from '@/services/preset/enhance-rules'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const { editorConfig, patchWorkflow } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)

  const interpolationOnnxModels = computed(
    () => envStore.env.checkResult?.onnxModels?.interpolation ?? [],
  )
  const superResolutionOnnxModels = computed(
    () => envStore.env.checkResult?.onnxModels?.super_resolution ?? [],
  )
  const interpolationAlgorithms = computed(
    () => envStore.env.checkResult?.interpolationAlgorithms ?? [],
  )
  const superResolutionAlgorithms = computed(
    () => envStore.env.checkResult?.superResolutionAlgorithms ?? [],
  )
  const animeProfiles = computed(
    () => envStore.env.checkResult?.animeProfiles ?? [],
  )
  const isOnnxBackend = computed(() => workflow.value.interpolation.tensorBackend === 'onnx')

  const interpolationEnabled = computed({
    get: () => workflow.value.interpolation.enabled,
    set: (value: boolean) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.enabled = value }),
  })

  const interpolationBackend = computed({
    get: () => workflow.value.interpolation.tensorBackend as TensorBackend,
    set: (value: TensorBackend) => {
      patchWorkflow((c: WorkflowConfig) => {
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
    set: (value: InferenceEngine) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.engine = value }),
  })

  const interpolationAlgorithm = computed({
    get: () => workflow.value.interpolation.algorithm,
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => {
      c.interpolation.algorithm = value
      c.interpolation.model = pickDefaultInterpolationModel(envStore.env.checkResult, value)
    }),
  })

  const interpolationModels = computed(
    () =>
      interpolationAlgorithms.value.find((a) => a.name === workflow.value.interpolation.algorithm)
        ?.models ?? [],
  )

  const interpolationModel = computed({
    get: () => workflow.value.interpolation.model,
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.model = value }),
  })

  const interpolationOnnxModel = computed({
    get: () => workflow.value.interpolation.onnxModel ?? '',
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.onnxModel = value }),
  })

  const fpsMode = computed({
    get: () => workflow.value.fpsMode as FpsMode,
    set: (value: FpsMode) => patchWorkflow((c: WorkflowConfig) => { c.fpsMode = value }),
  })

  const targetFps = computed({
    get: () => workflow.value.interpolation.targetFps,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.targetFps = value }),
  })

  const interpolationMulti = computed({
    get: () => workflow.value.interpolation.multi,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.multi = value }),
  })

  const interpolationScale = computed({
    get: () => workflow.value.interpolation.scale,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.scale = value }),
  })

  const interpolationFp16 = computed({
    get: () => workflow.value.interpolation.fp16,
    set: (value: boolean) => patchWorkflow((c: WorkflowConfig) => { c.interpolation.fp16 = value }),
  })

  const superResolutionEnabled = computed({
    get: () => workflow.value.superResolution.enabled,
    set: (value: boolean) => patchWorkflow((c: WorkflowConfig) => { c.superResolution.enabled = value }),
  })

  const superResolutionScale = computed({
    get: () => workflow.value.superResolution.scaleFactor,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.superResolution.scaleFactor = value }),
  })

  const superResolutionAlgorithm = computed({
    get: () => workflow.value.superResolution.algorithm,
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => { c.superResolution.algorithm = value }),
  })

  const superResolutionOnnxModel = computed({
    get: () => workflow.value.superResolution.onnxModel ?? '',
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => { c.superResolution.onnxModel = value }),
  })

  const processOrder = computed({
    get: () => workflow.value.processOrder as ProcessOrder,
    set: (value: ProcessOrder) => patchWorkflow((c: WorkflowConfig) => { c.processOrder = value }),
  })

  const animeEnabled = computed({
    get: () => workflow.value.anime.enabled,
    set: (value: boolean) => patchWorkflow((c: WorkflowConfig) => { c.anime.enabled = value }),
  })

  const animeProfile = computed({
    get: () => workflow.value.anime.profile,
    set: (value: string) => patchWorkflow((c: WorkflowConfig) => { c.anime.profile = value }),
  })

  const animeDenoise = computed({
    get: () => workflow.value.anime.denoise,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.anime.denoise = value }),
  })

  const animeEdgeBoost = computed({
    get: () => workflow.value.anime.edgeBoost,
    set: (value: number) => patchWorkflow((c: WorkflowConfig) => { c.anime.edgeBoost = value }),
  })

  return reactive({
    interpolationOnnxModels,
    superResolutionOnnxModels,
    interpolationAlgorithms,
    superResolutionAlgorithms,
    animeProfiles,
    interpolationModels,
    isOnnxBackend,
    interpolationEnabled,
    interpolationBackend,
    interpolationEngine,
    interpolationAlgorithm,
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
