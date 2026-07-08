// pure: no Vue / no Pinia / no Tauri
// Derived read-model rules for the enhance form.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  combinedVramMetricRows,
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  metricRows,
  resolveMetricsForEngine,
  type MetricRow,
  type RuntimeMetricEstimate,
  type VideoDimensions,
} from '@/services/model-metrics'
import {
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-rules'

export interface EnhanceViewModelInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  currentInterpolationAlgorithm: AlgorithmInfo | undefined
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

export interface EnhanceViewModel {
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

function selectedModelDetail(
  details: ModelVariantInfo[],
  selected: string | null | undefined,
): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === (selected ?? ''))
}

function scaledDimensions(video: VideoDimensions, scale: number): VideoDimensions {
  return {
    width: Math.max(1, Math.round(video.width * scale)),
    height: Math.max(1, Math.round(video.height * scale)),
  }
}

export function buildEnhanceViewModel({
  workflow,
  activeVideoDimensions,
  currentInterpolationAlgorithm,
  currentSuperResolutionAlgorithm,
}: EnhanceViewModelInput): EnhanceViewModel {
  const interpolationModelDetails = currentInterpolationAlgorithm?.modelDetails ?? []
  const interpolationOnnxModelDetails = currentInterpolationAlgorithm?.onnxModelDetails ?? []
  const superResolutionModelDetails = currentSuperResolutionAlgorithm?.modelDetails ?? []
  const superResolutionOnnxModelDetails = currentSuperResolutionAlgorithm?.onnxModelDetails ?? []

  const currentInterpolationModelDetail = workflow.interpolation.tensorBackend === 'onnx'
    ? selectedModelDetail(interpolationOnnxModelDetails, workflow.interpolation.onnxModel)
    : selectedModelDetail(interpolationModelDetails, workflow.interpolation.model)
  const currentSuperResolutionModelDetail = workflow.superResolution.tensorBackend === 'onnx'
    ? selectedModelDetail(superResolutionOnnxModelDetails, workflow.superResolution.onnxModel)
    : superResolutionModelDetails[0]

  const currentInterpolationRuntimeDetail = resolveMetricsForEngine(
    currentInterpolationModelDetail,
    workflow.interpolation.engine,
  )
  const currentSuperResolutionRuntimeDetail = resolveMetricsForEngine(
    currentSuperResolutionModelDetail,
    workflow.superResolution.engine,
  )
  const superResolutionRuntimeFrameCount =
    currentSuperResolutionRuntimeDetail?.metrics.runtimeFrameCount ?? null
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
    interpolationModelDetails,
    interpolationOnnxModelDetails,
    superResolutionModelDetails,
    superResolutionOnnxModelDetails,
    currentInterpolationModelDetail,
    currentSuperResolutionModelDetail,
    currentInterpolationRuntimeDetail,
    currentSuperResolutionRuntimeDetail,
    superResolutionRuntimeFrameCount,
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
