// pure: no Vue / no Pinia / no Tauri
// Model detail and engine-specific runtime detail selection for enhance read models.

import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import { resolveMetricsForEngine } from '@/services/model-engine-metrics'

interface EnhanceModelSelectionInput {
  workflow: WorkflowConfig
  currentInterpolationAlgorithm: AlgorithmInfo | undefined
  currentSuperResolutionAlgorithm: AlgorithmInfo | undefined
}

interface EnhanceModelSelection {
  interpolationModelDetails: ModelVariantInfo[]
  interpolationOnnxModelDetails: ModelVariantInfo[]
  superResolutionModelDetails: ModelVariantInfo[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]
  currentInterpolationModelDetail: ModelVariantInfo | undefined
  currentSuperResolutionModelDetail: ModelVariantInfo | undefined
  currentInterpolationRuntimeDetail: ModelVariantInfo | null
  currentSuperResolutionRuntimeDetail: ModelVariantInfo | null
  superResolutionRuntimeFrameCount: number | null
}

function selectedModelDetail(
  details: ModelVariantInfo[],
  selected: string | null | undefined,
): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === (selected ?? ''))
}

export function buildEnhanceModelSelection({
  workflow,
  currentInterpolationAlgorithm,
  currentSuperResolutionAlgorithm,
}: EnhanceModelSelectionInput): EnhanceModelSelection {
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
  }
}
