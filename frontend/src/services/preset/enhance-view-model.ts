// pure: no Vue / no Pinia / no Tauri
// Derived read-model rules for the enhance form.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import type { MetricRow, RuntimeMetricEstimate, VideoDimensions } from '@/types/view/model-metrics'
import { buildEnhanceModelSelection } from './enhance-model-selection'
import { buildEnhanceRuntimeView } from './enhance-runtime-view'

interface EnhanceViewModelInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  currentInterpolationAlgorithm: AlgorithmInfo | undefined
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

interface EnhanceViewModel {
  interpolationModelDetails: ModelVariantInfo[]
  interpolationOnnxModelDetails: ModelVariantInfo[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]
  currentInterpolationModelDetail: ModelVariantInfo | undefined
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  isPaddleGanSuperResolution: boolean
  isSuperResolutionInputFramesEditable: boolean
  effectiveSuperResolutionNumFrames: number
  superResolutionFixedWindowRows: MetricRow[]
  interpolationInputDimensions: VideoDimensions | null
  interpolationRuntimeEstimate: RuntimeMetricEstimate | null
  interpolationMetricRows: MetricRow[]
  superResolutionMetricRows: MetricRow[]
  combinedPeakVramBytes: number | null
  combinedVramMetricRows: MetricRow[]
}

export function buildEnhanceViewModel({
  workflow,
  activeVideoDimensions,
  currentInterpolationAlgorithm,
  currentSuperResolutionAlgorithm,
}: EnhanceViewModelInput): EnhanceViewModel {
  const modelSelection = buildEnhanceModelSelection({
    workflow,
    currentInterpolationAlgorithm,
    currentSuperResolutionAlgorithm,
  })
  const runtimeView = buildEnhanceRuntimeView({
    workflow,
    activeVideoDimensions,
    currentSuperResolutionAlgorithm,
    currentInterpolationRuntimeDetail: modelSelection.currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail: modelSelection.currentSuperResolutionRuntimeDetail,
    superResolutionRuntimeFrameCount: modelSelection.superResolutionRuntimeFrameCount,
  })

  return {
    interpolationModelDetails: modelSelection.interpolationModelDetails,
    interpolationOnnxModelDetails: modelSelection.interpolationOnnxModelDetails,
    superResolutionOnnxModelDetails: modelSelection.superResolutionOnnxModelDetails,
    currentInterpolationModelDetail: modelSelection.currentInterpolationModelDetail,
    currentInterpolationRuntimeDetail: modelSelection.currentInterpolationRuntimeDetail,
    isPaddleGanSuperResolution: runtimeView.isPaddleGanSuperResolution,
    isSuperResolutionInputFramesEditable: runtimeView.isSuperResolutionInputFramesEditable,
    effectiveSuperResolutionNumFrames: runtimeView.effectiveSuperResolutionNumFrames,
    superResolutionFixedWindowRows: runtimeView.superResolutionFixedWindowRows,
    interpolationInputDimensions: runtimeView.interpolationInputDimensions,
    interpolationRuntimeEstimate: runtimeView.interpolationRuntimeEstimate,
    interpolationMetricRows: runtimeView.interpolationMetricRows,
    superResolutionMetricRows: runtimeView.superResolutionMetricRows,
    combinedPeakVramBytes: runtimeView.combinedPeakVramBytes,
    combinedVramMetricRows: runtimeView.combinedVramMetricRows,
  }
}
