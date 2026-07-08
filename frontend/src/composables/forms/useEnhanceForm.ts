// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 单字段 lens 走 ``field``;含副作用(切换 backend 时联动 onnxModel,
// 切换 algorithm 时重置 model 默认值)的两个 setter 走 ``effect``。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { createDraftEditor } from '@/composables/forms/lens'
import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'
import {
  applyInterpolationAlgorithmSelection,
  applyInterpolationBackendSelection,
  applyInterpolationEnabled,
  applySuperResolutionAlgorithmSelection,
  applySuperResolutionBackendSelection,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from '@/services/preset/enhance-workflow'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const { activeItem, editorConfig, patchWorkflowAndPreset } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)
  const patchEnhanceWorkflow = patchWorkflowAndPreset
  const { field, effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchEnhanceWorkflow,
  )

  // Phase 8 — 算法下拉列表按当前选中的 tensorBackend 过滤。
  // 没有 ``tensorBackends`` 字段的旧缓存(Phase 8 之前持久化的)
  // 退化为 ``[]``,这里 ``.includes(backend)`` 返回 false,意味着
  // "未声明支持 = 不显示";比错显示安全。
  const interpolationBackendValue = computed(() => workflow.value.interpolation.tensorBackend as TensorBackend)
  const superResolutionBackendValue = computed(() => workflow.value.superResolution.tensorBackend as TensorBackend)

  const interpolation = createAlgorithmLens(
    computed(() => envStore.env.checkResult?.interpolationAlgorithms ?? []),
    computed(() => workflow.value.interpolation.algorithm),
    interpolationBackendValue,
  )

  const superResolutionAlgorithmSpecs = computed(() => envStore.env.checkResult?.superResolutionAlgorithms ?? [])
  const superResolution = createAlgorithmLens(
    superResolutionAlgorithmSpecs,
    computed(() => workflow.value.superResolution.algorithm),
    superResolutionBackendValue,
  )

  const animeProfiles = computed(() => envStore.env.checkResult?.animeProfiles ?? [])
  const isInterpolationOnnxBackend = computed(() => interpolationBackendValue.value === 'onnx')
  const isSuperResolutionOnnxBackend = computed(() => superResolutionBackendValue.value === 'onnx')
  const currentInterpolationAlgorithm = interpolation.current
  const currentSuperResolutionAlgorithm = computed(() =>
    superResolutionAlgorithmSpecs.value.find((a) => a.name === workflow.value.superResolution.algorithm),
  )
  const activeVideoDimensions = computed(() => {
    const info = activeItem.value?.info
    if (!info) return null
    return { width: info.width, height: info.height }
  })
  const enhanceViewModel = computed(() =>
    buildEnhanceViewModel({
      workflow: workflow.value,
      activeVideoDimensions: activeVideoDimensions.value,
      currentInterpolationAlgorithm: currentInterpolationAlgorithm.value,
      currentSuperResolutionAlgorithm: currentSuperResolutionAlgorithm.value,
    }),
  )
  const interpolationModelDetails = computed(() => enhanceViewModel.value.interpolationModelDetails)
  const interpolationOnnxModelDetails = computed(() => enhanceViewModel.value.interpolationOnnxModelDetails)
  const superResolutionModelDetails = computed(() => enhanceViewModel.value.superResolutionModelDetails)
  const superResolutionOnnxModelDetails = computed(() => enhanceViewModel.value.superResolutionOnnxModelDetails)
  const currentInterpolationModelDetail = computed(() => enhanceViewModel.value.currentInterpolationModelDetail)
  const currentSuperResolutionModelDetail = computed(() => enhanceViewModel.value.currentSuperResolutionModelDetail)
  const currentInterpolationRuntimeDetail = computed(() => enhanceViewModel.value.currentInterpolationRuntimeDetail)
  const currentSuperResolutionRuntimeDetail = computed(() => enhanceViewModel.value.currentSuperResolutionRuntimeDetail)
  const interpolationRuntimeEstimate = computed(() => enhanceViewModel.value.interpolationRuntimeEstimate)
  const superResolutionRuntimeEstimate = computed(() => enhanceViewModel.value.superResolutionRuntimeEstimate)
  const interpolationMetricRows = computed(() => enhanceViewModel.value.interpolationMetricRows)
  const superResolutionMetricRows = computed(() => enhanceViewModel.value.superResolutionMetricRows)
  const combinedPeakVramBytes = computed(() => enhanceViewModel.value.combinedPeakVramBytes)
  const combinedVramRows = computed(() => enhanceViewModel.value.combinedVramMetricRows)
  const isSuperResolutionInputFramesEditable = computed(() =>
    enhanceViewModel.value.isSuperResolutionInputFramesEditable,
  )
  const superResolutionFixedWindowRows = computed(() => enhanceViewModel.value.superResolutionFixedWindowRows)
  const isPaddleGanSuperResolution = computed(() => enhanceViewModel.value.isPaddleGanSuperResolution)

  // ── 纯字段 lens(读写同一处) ────────────────────────────────────────────
  const interpolationEnabled = effect<boolean>(
    () => workflow.value.interpolation.enabled,
    (value) => patchEnhanceWorkflow((c) => {
      applyInterpolationEnabled(c, value, envStore.env.checkResult)
    }),
  )
  const interpolationEngine = field(
    (c) => (c.interpolation.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.interpolation.engine = v },
  )
  const interpolationModel = field(
    (c) => c.interpolation.model,
    (c, v: string) => { c.interpolation.model = v },
  )
  const interpolationOnnxModel = field(
    (c) => c.interpolation.onnxModel ?? '',
    (c, v: string) => { c.interpolation.onnxModel = v },
  )
  const fpsMode = field(
    (c) => c.fpsMode as FpsMode,
    (c, v: FpsMode) => { c.fpsMode = v },
  )
  const targetFps = field(
    (c) => c.interpolation.targetFps,
    (c, v: number) => { c.interpolation.targetFps = v },
  )
  const interpolationMulti = field(
    (c) => c.interpolation.multi,
    (c, v: number) => { c.interpolation.multi = v },
  )
  const interpolationScale = field(
    (c) => c.interpolation.scale,
    (c, v: number) => { c.interpolation.scale = v },
  )
  const interpolationFp16 = field(
    (c) => c.interpolation.fp16,
    (c, v: boolean) => { c.interpolation.fp16 = v },
  )
  const superResolutionEnabled = effect<boolean>(
    () => workflow.value.superResolution.enabled,
    (value) => patchEnhanceWorkflow((c) => {
      applySuperResolutionEnabled(c, value, envStore.env.checkResult)
    }),
  )
  const superResolutionEngine = field(
    (c) => (c.superResolution.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.superResolution.engine = v },
  )
  const superResolutionScale = effect<number>(
    () => workflow.value.superResolution.scaleFactor,
    (value) => patchEnhanceWorkflow((c) => {
      applySuperResolutionScale(c, value, envStore.env.checkResult)
    }),
  )
  const superResolutionOnnxModel = field(
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
  )
  const superResolutionNumFrames = effect<number>(
    () => enhanceViewModel.value.effectiveSuperResolutionNumFrames,
    (value) => patchEnhanceWorkflow((c) => {
      applySuperResolutionNumFrames(c, value, envStore.env.checkResult)
    }),
  )
  const processOrder = field(
    (c) => c.processOrder as ProcessOrder,
    (c, v: ProcessOrder) => { c.processOrder = v },
  )
  const animeEnabled = field(
    (c) => c.anime.enabled,
    (c, v: boolean) => { c.anime.enabled = v },
  )
  const animeProfile = field(
    (c) => c.anime.profile,
    (c, v: string) => { c.anime.profile = v },
  )
  const animeDenoise = field(
    (c) => c.anime.denoise,
    (c, v: number) => { c.anime.denoise = v },
  )
  const animeEdgeBoost = field(
    (c) => c.anime.edgeBoost,
    (c, v: number) => { c.anime.edgeBoost = v },
  )

  // ── 复合 setter(切换时联动其他字段) ────────────────────────────────────
  const interpolationBackend = effect<TensorBackend>(
    () => workflow.value.interpolation.tensorBackend as TensorBackend,
    (value) => patchEnhanceWorkflow((c) => {
      applyInterpolationBackendSelection(c, value, envStore.env.checkResult)
    }),
  )

  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchEnhanceWorkflow((c) => {
      applySuperResolutionBackendSelection(c, value, envStore.env.checkResult)
    }),
  )

  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchEnhanceWorkflow((c) => {
      applyInterpolationAlgorithmSelection(c, value, envStore.env.checkResult)
    }),
  )

  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchEnhanceWorkflow((c) => {
      applySuperResolutionAlgorithmSelection(c, value, envStore.env.checkResult)
    }),
  )

  return reactive({
    interpolationOnnxModels: interpolation.onnxModels,
    superResolutionOnnxModels: superResolution.onnxModels,
    interpolationAlgorithms: interpolation.algorithms,
    superResolutionAlgorithms: superResolution.algorithms,
    animeProfiles,
    interpolationModels: interpolation.models,
    interpolationModelDetails,
    interpolationOnnxModelDetails,
    superResolutionModelDetails,
    superResolutionOnnxModelDetails,
    currentInterpolationModelDetail,
    currentSuperResolutionModelDetail,
    currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail,
    interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate,
    interpolationMetricRows,
    superResolutionMetricRows,
    combinedPeakVramBytes,
    combinedVramMetricRows: combinedVramRows,
    isSuperResolutionInputFramesEditable,
    superResolutionInputFramesLabel: '每块输入帧数',
    superResolutionInputFramesHint: '每次送入超分模型的连续输入帧数，会影响显存；不是邻帧窗口。',
    superResolutionFixedWindowRows,
    isOnnxBackend: isInterpolationOnnxBackend,
    isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend,
    isPaddleGanSuperResolution,
    currentSuperResolutionAlgorithm,
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
    superResolutionBackend,
    superResolutionEngine,
    superResolutionScale,
    superResolutionAlgorithm,
    superResolutionOnnxModel,
    superResolutionNumFrames,
    processOrder,
    animeEnabled,
    animeProfile,
    animeDenoise,
    animeEdgeBoost,
  })
}
