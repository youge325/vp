import { computed, type ComputedRef } from 'vue'

import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'
import type { VideoDimensions } from '@/services/model-runtime-estimates'
import type { AlgorithmInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'

interface EnhanceViewBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  activeVideoDimensions: ComputedRef<VideoDimensions | null>
  currentInterpolationAlgorithm: ComputedRef<AlgorithmInfo | undefined>
  currentSuperResolutionAlgorithm: ComputedRef<AlgorithmInfo | undefined>
}

export function createEnhanceViewBindings({
  workflow,
  activeVideoDimensions,
  currentInterpolationAlgorithm,
  currentSuperResolutionAlgorithm,
}: EnhanceViewBindingParams) {
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
  const effectiveSuperResolutionNumFrames = computed(() => enhanceViewModel.value.effectiveSuperResolutionNumFrames)

  return {
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
    isPaddleGanSuperResolution,
    effectiveSuperResolutionNumFrames,
  }
}
