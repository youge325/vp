// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 单字段双向绑定走 ``fieldLens``;含副作用(切换 backend 时联动 onnxModel,
// 切换 algorithm 时重置 model 默认值)的两个 setter 仍显式写出。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { fieldLens } from '@/composables/forms/lens'
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
  const getWorkflow = () => workflow.value

  const interpolationAlgorithms = computed(
    () => envStore.env.checkResult?.interpolationAlgorithms ?? [],
  )
  const superResolutionAlgorithms = computed(
    () => envStore.env.checkResult?.superResolutionAlgorithms ?? [],
  )
  const animeProfiles = computed(
    () => envStore.env.checkResult?.animeProfiles ?? [],
  )
  const interpolationOnnxModels = computed(() => {
    const alg = interpolationAlgorithms.value.find(
      (a) => a.name === workflow.value.interpolation.algorithm,
    )
    return alg?.onnxModels ?? []
  })
  const superResolutionOnnxModels = computed(() => {
    const alg = superResolutionAlgorithms.value.find(
      (a) => a.name === workflow.value.superResolution.algorithm,
    )
    return alg?.onnxModels ?? []
  })
  const isOnnxBackend = computed(() => workflow.value.interpolation.tensorBackend === 'onnx')

  // 单字段透传 lens
  const interpolationEnabled = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.enabled,
    (c, v) => { c.interpolation.enabled = v },
  )

  // 复合 setter:切换 backend 时同步 engine 与 onnx 模型默认值
  const interpolationBackend = computed({
    get: () => workflow.value.interpolation.tensorBackend as TensorBackend,
    set: (value: TensorBackend) => {
      patchWorkflow((c: WorkflowConfig) => {
        c.interpolation.tensorBackend = value
        c.interpolation.engine = pickDefaultEngine(envStore.env.checkResult, value) ?? c.interpolation.engine
        if (value === 'onnx') {
          c.interpolation.onnxModel = fallbackInterpolationOnnxModel(envStore.env.checkResult, c.interpolation.algorithm, c.interpolation.onnxModel)
          c.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(envStore.env.checkResult, c.superResolution.algorithm, c.superResolution.onnxModel)
        }
      })
    },
  })

  const interpolationEngine = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => (c.interpolation.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.interpolation.engine = v },
  )

  // 复合 setter:切换 algorithm 时联动 model 默认值
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

  const interpolationModel = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.model,
    (c, v: string) => { c.interpolation.model = v },
  )

  const interpolationOnnxModel = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.onnxModel ?? '',
    (c, v: string) => { c.interpolation.onnxModel = v },
  )

  const fpsMode = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.fpsMode as FpsMode,
    (c, v: FpsMode) => { c.fpsMode = v },
  )

  const targetFps = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.targetFps,
    (c, v: number) => { c.interpolation.targetFps = v },
  )

  const interpolationMulti = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.multi,
    (c, v: number) => { c.interpolation.multi = v },
  )

  const interpolationScale = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.scale,
    (c, v: number) => { c.interpolation.scale = v },
  )

  const interpolationFp16 = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.interpolation.fp16,
    (c, v: boolean) => { c.interpolation.fp16 = v },
  )

  const superResolutionEnabled = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.superResolution.enabled,
    (c, v: boolean) => { c.superResolution.enabled = v },
  )

  const superResolutionScale = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.superResolution.scaleFactor,
    (c, v: number) => { c.superResolution.scaleFactor = v },
  )

  const superResolutionAlgorithm = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.superResolution.algorithm,
    (c, v: string) => { c.superResolution.algorithm = v },
  )

  const superResolutionOnnxModel = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
  )

  const processOrder = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.processOrder as ProcessOrder,
    (c, v: ProcessOrder) => { c.processOrder = v },
  )

  const animeEnabled = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.anime.enabled,
    (c, v: boolean) => { c.anime.enabled = v },
  )

  const animeProfile = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.anime.profile,
    (c, v: string) => { c.anime.profile = v },
  )

  const animeDenoise = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.anime.denoise,
    (c, v: number) => { c.anime.denoise = v },
  )

  const animeEdgeBoost = fieldLens(
    getWorkflow,
    patchWorkflow,
    (c) => c.anime.edgeBoost,
    (c, v: number) => { c.anime.edgeBoost = v },
  )

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
