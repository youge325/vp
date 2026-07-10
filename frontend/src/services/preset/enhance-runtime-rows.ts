// pure: no Vue / no Pinia / no Tauri
// Runtime row and fixed-window state rules for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import type { MetricRow, RuntimeMetricEstimate } from '@/types/view/model-metrics'
import { combinedVramMetricRows, metricRows } from '@/services/model-metric-rows'
import {
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-algorithm-capabilities'

interface EnhanceRuntimeFrameStateInput {
  workflow: WorkflowConfig
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

interface EnhanceRuntimeFrameState {
  isPaddleGanSuperResolution: boolean
  isSuperResolutionInputFramesEditable: boolean
  effectiveSuperResolutionNumFrames: number
  superResolutionFixedWindowRows: MetricRow[]
}

interface EnhanceRuntimeRowsInput {
  workflow: WorkflowConfig
  frameState: EnhanceRuntimeFrameState
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  interpolationRuntimeEstimate: RuntimeMetricEstimate | null
  superResolutionRuntimeEstimate: RuntimeMetricEstimate | null
  combinedPeakVramBytes: number | null
}

interface EnhanceRuntimeRows extends EnhanceRuntimeFrameState {
  interpolationMetricRows: MetricRow[]
  superResolutionMetricRows: MetricRow[]
  combinedVramMetricRows: MetricRow[]
}

export function buildEnhanceRuntimeFrameState({
  workflow,
  currentSuperResolutionAlgorithm,
}: EnhanceRuntimeFrameStateInput): EnhanceRuntimeFrameState {
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

  return {
    isPaddleGanSuperResolution,
    isSuperResolutionInputFramesEditable,
    effectiveSuperResolutionNumFrames,
    superResolutionFixedWindowRows,
  }
}

export function buildEnhanceRuntimeRows({
  workflow,
  frameState,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  interpolationRuntimeEstimate,
  superResolutionRuntimeEstimate,
  combinedPeakVramBytes,
}: EnhanceRuntimeRowsInput): EnhanceRuntimeRows {
  const interpolationMetricRows = metricRows(currentInterpolationRuntimeDetail, interpolationRuntimeEstimate)
  const superResolutionMetricRows = metricRows(currentSuperResolutionRuntimeDetail, superResolutionRuntimeEstimate)
  const combinedRows =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? combinedVramMetricRows(combinedPeakVramBytes)
      : []

  return {
    ...frameState,
    interpolationMetricRows,
    superResolutionMetricRows,
    combinedVramMetricRows: combinedRows,
  }
}
