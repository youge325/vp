// pure: no Vue / no Pinia / no Tauri
// Runtime row and fixed-window state rules for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  combinedVramMetricRows,
  metricRows,
  type MetricRow,
} from '@/services/model-metric-rows'
import {
  type RuntimeMetricEstimate,
} from '@/services/model-runtime-estimates'
import {
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-algorithm-capabilities'

export type { MetricRow }

export interface EnhanceRuntimeFrameStateInput {
  workflow: WorkflowConfig
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

export interface EnhanceRuntimeFrameState {
  isPaddleGanSuperResolution: boolean
  isSuperResolutionInputFramesEditable: boolean
  effectiveSuperResolutionNumFrames: number
  superResolutionFixedWindowRows: MetricRow[]
}

export interface EnhanceRuntimeRowsInput extends EnhanceRuntimeFrameStateInput {
  frameState?: EnhanceRuntimeFrameState
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  interpolationRuntimeEstimate: RuntimeMetricEstimate | null
  superResolutionRuntimeEstimate: RuntimeMetricEstimate | null
  combinedPeakVramBytes: number | null
}

export interface EnhanceRuntimeRows extends EnhanceRuntimeFrameState {
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
  currentSuperResolutionAlgorithm,
  frameState,
  currentInterpolationRuntimeDetail,
  currentSuperResolutionRuntimeDetail,
  interpolationRuntimeEstimate,
  superResolutionRuntimeEstimate,
  combinedPeakVramBytes,
}: EnhanceRuntimeRowsInput): EnhanceRuntimeRows {
  const resolvedFrameState =
    frameState ?? buildEnhanceRuntimeFrameState({ workflow, currentSuperResolutionAlgorithm })
  const interpolationMetricRows = metricRows(currentInterpolationRuntimeDetail, interpolationRuntimeEstimate)
  const superResolutionMetricRows = metricRows(currentSuperResolutionRuntimeDetail, superResolutionRuntimeEstimate)
  const combinedRows =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? combinedVramMetricRows(combinedPeakVramBytes)
      : []

  return {
    ...resolvedFrameState,
    interpolationMetricRows,
    superResolutionMetricRows,
    combinedVramMetricRows: combinedRows,
  }
}
