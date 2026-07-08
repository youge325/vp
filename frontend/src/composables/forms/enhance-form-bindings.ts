import { computed, reactive, type ComputedRef } from 'vue'
import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import { createDraftEditor } from '@/composables/forms/lens'
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
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

interface VideoDimensions {
  width: number
  height: number
}

export interface EnhanceFormBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  activeVideoDimensions: ComputedRef<VideoDimensions | null>
  patchWorkflow: (mutator: (workflow: WorkflowConfig) => void) => void
}

export function createEnhanceFormBindings({
  workflow,
  checkResult,
  activeVideoDimensions,
  patchWorkflow,
}: EnhanceFormBindingParams) {
  const { field, effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflow,
  )

  const interpolationBackendValue = computed(() => workflow.value.interpolation.tensorBackend as TensorBackend)
  const superResolutionBackendValue = computed(() => workflow.value.superResolution.tensorBackend as TensorBackend)

  const interpolation = createAlgorithmLens(
    computed(() => checkResult.value?.interpolationAlgorithms ?? []),
    computed(() => workflow.value.interpolation.algorithm),
    interpolationBackendValue,
  )

  const superResolutionAlgorithmSpecs = computed(() => checkResult.value?.superResolutionAlgorithms ?? [])
  const superResolution = createAlgorithmLens(
    superResolutionAlgorithmSpecs,
    computed(() => workflow.value.superResolution.algorithm),
    superResolutionBackendValue,
  )

  const animeProfiles = computed(() => checkResult.value?.animeProfiles ?? [])
  const isInterpolationOnnxBackend = computed(() => interpolationBackendValue.value === 'onnx')
  const isSuperResolutionOnnxBackend = computed(() => superResolutionBackendValue.value === 'onnx')
  const currentInterpolationAlgorithm = interpolation.current
  const currentSuperResolutionAlgorithm = computed(() =>
    superResolutionAlgorithmSpecs.value.find((a) => a.name === workflow.value.superResolution.algorithm),
  )
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

  const interpolationEnabled = effect<boolean>(
    () => workflow.value.interpolation.enabled,
    (value) => patchWorkflow((c) => {
      applyInterpolationEnabled(c, value, checkResult.value)
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
    (value) => patchWorkflow((c) => {
      applySuperResolutionEnabled(c, value, checkResult.value)
    }),
  )
  const superResolutionEngine = field(
    (c) => (c.superResolution.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.superResolution.engine = v },
  )
  const superResolutionScale = effect<number>(
    () => workflow.value.superResolution.scaleFactor,
    (value) => patchWorkflow((c) => {
      applySuperResolutionScale(c, value, checkResult.value)
    }),
  )
  const superResolutionOnnxModel = field(
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
  )
  const superResolutionNumFrames = effect<number>(
    () => enhanceViewModel.value.effectiveSuperResolutionNumFrames,
    (value) => patchWorkflow((c) => {
      applySuperResolutionNumFrames(c, value, checkResult.value)
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

  const interpolationBackend = effect<TensorBackend>(
    () => workflow.value.interpolation.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applyInterpolationBackendSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applySuperResolutionBackendSelection(c, value, checkResult.value)
    }),
  )
  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      applyInterpolationAlgorithmSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchWorkflow((c) => {
      applySuperResolutionAlgorithmSelection(c, value, checkResult.value)
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
