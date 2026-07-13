// pure: no Vue / no Pinia / no Tauri
// Runtime estimate and metric row derivation for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import type { VideoDimensions } from '@/types/view/model-metrics'
import { buildEnhanceRuntimeEstimates } from './enhance-runtime-estimates'
import { buildEnhanceRuntimeFrameState, buildEnhanceRuntimeRows } from './enhance-runtime-rows'

interface EnhanceRuntimeViewInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  superResolutionRuntimeFrameCount: number | null
}

export function buildEnhanceRuntimeView({
  workflow,
  activeVideoDimensions,
  currentSuperResolutionAlgorithm,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  superResolutionRuntimeFrameCount,
}: EnhanceRuntimeViewInput) {
  const frameState = buildEnhanceRuntimeFrameState({ workflow, currentSuperResolutionAlgorithm })
  const estimates = buildEnhanceRuntimeEstimates({
    workflow,
    activeVideoDimensions,
    isSuperResolutionInputFramesEditable: frameState.isSuperResolutionInputFramesEditable,
    currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail,
    superResolutionRuntimeFrameCount,
  })
  const rows = buildEnhanceRuntimeRows({
    workflow,
    frameState,
    currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail,
    interpolationRuntimeEstimate: estimates.interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate: estimates.superResolutionRuntimeEstimate,
    combinedPeakVramBytes: estimates.combinedPeakVramBytes,
  })

  return {
    ...rows,
    interpolationInputDimensions: estimates.interpolationInputDimensions,
    interpolationRuntimeEstimate: estimates.interpolationRuntimeEstimate,
    combinedPeakVramBytes: estimates.combinedPeakVramBytes,
  }
}
