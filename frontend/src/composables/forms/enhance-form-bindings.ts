import { computed, reactive, type ComputedRef } from 'vue'
import { createEnhanceFieldBindings } from '@/composables/forms/enhance-field-bindings'
import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
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
  const fieldBindings = createEnhanceFieldBindings({
    workflow,
    checkResult,
    effectiveSuperResolutionNumFrames: computed(() => enhanceViewModel.value.effectiveSuperResolutionNumFrames),
    patchWorkflow,
  })

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
    ...fieldBindings,
  })
}
