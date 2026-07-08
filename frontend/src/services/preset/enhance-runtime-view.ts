// pure: no Vue / no Pinia / no Tauri
// Runtime estimate and metric row derivation for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  combinedVramMetricRows,
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  metricRows,
  type MetricRow,
  type RuntimeMetricEstimate,
  type VideoDimensions,
} from '@/services/model-metrics'
import {
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-algorithm-capabilities'

export type { MetricRow, RuntimeMetricEstimate, VideoDimensions }

export interface EnhanceRuntimeViewInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  superResolutionRuntimeFrameCount: number | null
}

export interface EnhanceRuntimeView {
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

function scaledDimensions(video: VideoDimensions, scale: number): VideoDimensions {
  return {
    width: Math.max(1, Math.round(video.width * scale)),
    height: Math.max(1, Math.round(video.height * scale)),
  }
}

export function buildEnhanceRuntimeView({
  workflow,
  activeVideoDimensions,
  currentSuperResolutionAlgorithm,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  superResolutionRuntimeFrameCount,
}: EnhanceRuntimeViewInput): EnhanceRuntimeView {
  const isPaddleGanSuperResolution = isPaddleGanVsrAlgorithm(currentSuperResolutionAlgorithm)
  const isSuperResolutionInputFramesEditable =
    superResolutionInputFrameMode(currentSuperResolutionAlgorithm) === 'editable_chunk'
  const effectiveSuperResolutionNumFrames =
    fixedRuntimeFrameCount(currentSuperResolutionAlgorithm) ??
    workflow.superResolution.numFrames ??
    10
  const superResolutionFixedWindowRows =
    isPaddleGanSuperResolution && !isSuperResolutionInputFramesEditable && effectiveSuperResolutionNumFrames
      ? [{ label: '邻帧窗口', value: `${effectiveSuperResolutionNumFrames} 帧（固定）` }]
      : []

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
  const interpolationMetricRows = metricRows(currentInterpolationRuntimeDetail, interpolationRuntimeEstimate)
  const superResolutionMetricRows = metricRows(currentSuperResolutionRuntimeDetail, superResolutionRuntimeEstimate)
  const combinedPeakVramBytes =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? estimateCombinedPeakVram(interpolationRuntimeEstimate, superResolutionRuntimeEstimate)
      : null
  const combinedRows =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? combinedVramMetricRows(combinedPeakVramBytes)
      : []

  return {
    isPaddleGanSuperResolution,
    isSuperResolutionInputFramesEditable,
    effectiveSuperResolutionNumFrames,
    superResolutionFixedWindowRows,
    interpolationInputDimensions,
    interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate,
    interpolationMetricRows,
    superResolutionMetricRows,
    combinedPeakVramBytes,
    combinedVramMetricRows: combinedRows,
  }
}
