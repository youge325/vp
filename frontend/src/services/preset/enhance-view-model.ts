// pure: no Vue / no Pinia / no Tauri
// Derived read-model rules for the enhance form.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import type { MetricRow } from '@/services/model-metric-rows'
import type { RuntimeMetricEstimate, VideoDimensions } from '@/services/model-runtime-estimates'
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
  superResolutionModelDetails: ModelVariantInfo[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]
  currentInterpolationModelDetail: ModelVariantInfo | undefined
  currentSuperResolutionModelDetail: ModelVariantInfo | undefined
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  superResolutionRuntimeFrameCount: number | null
  isPaddleGanSuperResolution: boolean
  isSuperResolutionInputFramesEditable: boolean
  effectiveSuperResolutionNumFrames: number
  superResolutionFixedWindowRows: MetricRow[]
  interpolationInputDimensions: VideoDimensions | null
  interpolationRuntimeEstimate: RuntimeMetricEstimate | null
  superResolutionRuntimeEstimate: RuntimeMetricEstimate | null
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
    ...modelSelection,
    ...runtimeView,
  }
}
