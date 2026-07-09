// pure: no Vue / no Pinia / no Tauri
// Runtime estimate and metric row derivation for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import type { MetricRow } from '@/services/model-metric-rows'
import type { RuntimeMetricEstimate, VideoDimensions } from '@/services/model-runtime-estimates'
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

interface EnhanceRuntimeView {
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

export function buildEnhanceRuntimeView({
  workflow,
  activeVideoDimensions,
  currentSuperResolutionAlgorithm,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  superResolutionRuntimeFrameCount,
}: EnhanceRuntimeViewInput): EnhanceRuntimeView {
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
    currentSuperResolutionAlgorithm,
    frameState,
    currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail,
    interpolationRuntimeEstimate: estimates.interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate: estimates.superResolutionRuntimeEstimate,
    combinedPeakVramBytes: estimates.combinedPeakVramBytes,
  })

  return {
    ...rows,
    ...estimates,
  }
}
