// Pure enhance read model: model selection, frame policy, estimates and rows.

import type {
  AlgorithmInfo,
  ModelLicenseInfo,
  ModelVariantInfo,
  WorkflowConfig,
} from '@/types/protocol'
import type { MetricRow, VideoDimensions } from '@/types/view/model-metrics'
import { APPLICATION_DEFAULTS } from '@/types/protocol'
import { resolveMetricsForEngine } from '@/services/model-engine-metrics'
import {
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
} from '@/services/model-runtime-estimates'
import {
  combinedVramMetricRows,
  metricRows,
} from '@/services/model-metric-rows'
import {
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-algorithm-capabilities'

export interface EnhanceReadModelInput {
  workflow: WorkflowConfig
  activeVideoDimensions: VideoDimensions | null
  currentInterpolationAlgorithm: AlgorithmInfo | undefined
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

export interface EnhanceReadModel {
  interpolationModelDetails: ModelVariantInfo[]
  interpolationOnnxModelDetails: ModelVariantInfo[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]
  isSuperResolutionScaleLocked: boolean
  superResolutionModelLicense: ModelLicenseInfo | null
  isSuperResolutionInputFramesEditable: boolean
  effectiveSuperResolutionNumFrames: number
  superResolutionFixedWindowRows: MetricRow[]
  interpolationMetricRows: MetricRow[]
  superResolutionMetricRows: MetricRow[]
  combinedVramMetricRows: MetricRow[]
}

function selectedModelDetail(
  details: readonly ModelVariantInfo[],
  selected: string | null | undefined,
): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === (selected ?? ''))
}

function scaledDimensions(
  video: VideoDimensions,
  scale: number,
): VideoDimensions {
  return {
    width: Math.max(1, Math.round(video.width * scale)),
    height: Math.max(1, Math.round(video.height * scale)),
  }
}

export function buildEnhanceReadModel({
  workflow,
  activeVideoDimensions,
  currentInterpolationAlgorithm,
  currentSuperResolutionAlgorithm,
}: EnhanceReadModelInput): EnhanceReadModel {
  const interpolationModelDetails = currentInterpolationAlgorithm?.modelDetails ?? []
  const interpolationOnnxModelDetails = currentInterpolationAlgorithm?.onnxModelDetails ?? []
  const superResolutionModelDetails = currentSuperResolutionAlgorithm?.modelDetails ?? []
  const superResolutionOnnxModelDetails = currentSuperResolutionAlgorithm?.onnxModelDetails ?? []

  const interpolationDetail = workflow.interpolation.tensorBackend === 'onnx'
    ? selectedModelDetail(interpolationOnnxModelDetails, workflow.interpolation.onnxModel)
    : selectedModelDetail(interpolationModelDetails, workflow.interpolation.model)
  const superResolutionDetail = workflow.superResolution.tensorBackend === 'onnx'
    ? selectedModelDetail(superResolutionOnnxModelDetails, workflow.superResolution.onnxModel)
    : selectedModelDetail(
      superResolutionModelDetails,
      `x${workflow.superResolution.scaleFactor}`,
    ) ?? superResolutionModelDetails[0]
  const interpolationRuntimeDetail = resolveMetricsForEngine(
    interpolationDetail,
    workflow.interpolation.engine,
  )
  const superResolutionRuntimeDetail = resolveMetricsForEngine(
    superResolutionDetail,
    workflow.superResolution.engine,
  )

  const isPaddleGanSuperResolution = isPaddleGanVsrAlgorithm(currentSuperResolutionAlgorithm)
  const isSuperResolutionScaleLocked = currentSuperResolutionAlgorithm?.scaleFactors.length === 1
  const isSuperResolutionInputFramesEditable =
    superResolutionInputFrameMode(currentSuperResolutionAlgorithm) === 'editable_chunk'
  const effectiveSuperResolutionNumFrames =
    fixedRuntimeFrameCount(currentSuperResolutionAlgorithm)
    ?? workflow.superResolution.numFrames
    ?? APPLICATION_DEFAULTS.superResolution.numFrames
  const superResolutionFixedWindowRows =
    isPaddleGanSuperResolution && !isSuperResolutionInputFramesEditable
      ? [{ label: '邻帧窗口', value: `${effectiveSuperResolutionNumFrames} 帧（固定）` }]
      : []

  const interpolationInputDimensions =
    activeVideoDimensions
    && workflow.superResolution.enabled
    && workflow.processOrder === 'super_resolution_then_interpolation'
      ? scaledDimensions(activeVideoDimensions, workflow.superResolution.scaleFactor || 1)
      : activeVideoDimensions
  const interpolationRuntimeEstimate = estimateModelRuntimeMetrics(
    interpolationRuntimeDetail,
    interpolationInputDimensions,
    {
      scale: workflow.interpolation.scale || APPLICATION_DEFAULTS.interpolation.scale,
      precisionBytes: workflow.interpolation.fp16 ? 2 : 4,
      temporalFrames: 1,
    },
  )
  const superResolutionRuntimeEstimate = estimateModelRuntimeMetrics(
    superResolutionRuntimeDetail,
    activeVideoDimensions,
    {
      scale: 1,
      precisionBytes: 4,
      temporalFrames: isSuperResolutionInputFramesEditable
        ? workflow.superResolution.numFrames ?? APPLICATION_DEFAULTS.superResolution.numFrames
        : 1,
      runtimeFrameCount: superResolutionRuntimeDetail?.metrics.runtimeFrameCount ?? null,
    },
  )
  const combinedPeakVramBytes =
    workflow.interpolation.enabled && workflow.superResolution.enabled
      ? estimateCombinedPeakVram(interpolationRuntimeEstimate, superResolutionRuntimeEstimate)
      : null

  return {
    interpolationModelDetails,
    interpolationOnnxModelDetails,
    superResolutionOnnxModelDetails,
    isSuperResolutionScaleLocked,
    superResolutionModelLicense: currentSuperResolutionAlgorithm?.modelLicense ?? null,
    isSuperResolutionInputFramesEditable,
    effectiveSuperResolutionNumFrames,
    superResolutionFixedWindowRows,
    interpolationMetricRows: metricRows(interpolationRuntimeDetail, interpolationRuntimeEstimate),
    superResolutionMetricRows: metricRows(superResolutionRuntimeDetail, superResolutionRuntimeEstimate),
    combinedVramMetricRows:
      workflow.interpolation.enabled && workflow.superResolution.enabled
        ? combinedVramMetricRows(combinedPeakVramBytes)
        : [],
  }
}
