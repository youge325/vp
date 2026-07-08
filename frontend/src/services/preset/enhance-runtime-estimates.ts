// pure: no Vue / no Pinia / no Tauri
// Runtime estimate rules for enhance read models.

import type { ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  type RuntimeMetricEstimate,
  type VideoDimensions,
} from '@/services/model-runtime-estimates'

export type { RuntimeMetricEstimate, VideoDimensions }

export interface EnhanceRuntimeEstimatesInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  isSuperResolutionInputFramesEditable: boolean
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  superResolutionRuntimeFrameCount: number | null
}

export interface EnhanceRuntimeEstimates {
  interpolationInputDimensions: VideoDimensions | null
  interpolationRuntimeEstimate: RuntimeMetricEstimate | null
  superResolutionRuntimeEstimate: RuntimeMetricEstimate | null
  combinedPeakVramBytes: number | null
}

function scaledDimensions(video: VideoDimensions, scale: number): VideoDimensions {
  return {
    width: Math.max(1, Math.round(video.width * scale)),
    height: Math.max(1, Math.round(video.height * scale)),
  }
}

export function buildEnhanceRuntimeEstimates({
  workflow,
  activeVideoDimensions,
  isSuperResolutionInputFramesEditable,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  superResolutionRuntimeFrameCount,
}: EnhanceRuntimeEstimatesInput): EnhanceRuntimeEstimates {
  const interpolationInputDimensions =
    activeVideoDimensions &&
    workflow.superResolution.enabled &&
    workflow.processOrder === 'super_resolution_then_interpolation'
      ? scaledDimensions(activeVideoDimensions, workflow.superResolution.scaleFactor || 1)
      : activeVideoDimensions

  const interpolationRuntimeEstimate = estimateModelRuntimeMetrics(
    currentInterpolationRuntimeDetail,
    interpolationInputDimensions,
    {
      scale: workflow.interpolation.scale || 1,
      precisionBytes: workflow.interpolation.fp16 ? 2 : 4,
      temporalFrames: 1,
    },
  )
  const superResolutionRuntimeEstimate = estimateModelRuntimeMetrics(
    currentSuperResolutionRuntimeDetail,
    activeVideoDimensions,
    {
      scale: 1,
      precisionBytes: 4,
      temporalFrames: isSuperResolutionInputFramesEditable ? workflow.superResolution.numFrames ?? 10 : 1,
      runtimeFrameCount: superResolutionRuntimeFrameCount,
    },
  )
  const combinedPeakVramBytes =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? estimateCombinedPeakVram(interpolationRuntimeEstimate, superResolutionRuntimeEstimate)
      : null

  return {
    interpolationInputDimensions,
    interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate,
    combinedPeakVramBytes,
  }
}
