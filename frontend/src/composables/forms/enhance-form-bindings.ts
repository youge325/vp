import { reactive, type ComputedRef } from 'vue'
import { createEnhanceAlgorithmBindings } from '@/composables/forms/enhance-algorithm-bindings'
import { createEnhanceEffectBindings } from '@/composables/forms/enhance-effect-bindings'
import { createEnhanceScalarFieldBindings } from '@/composables/forms/enhance-scalar-field-bindings'
import { createEnhanceViewBindings } from '@/composables/forms/enhance-view-bindings'
import type { VideoDimensions } from '@/types/view/model-metrics'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'

interface EnhanceFormBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  activeVideoDimensions: ComputedRef<VideoDimensions | null>
  patchWorkflow: (mutator: (workflow: WorkflowConfig) => void) => void
}

export function createEnhanceFormBindings({
  workflow,
  checkResult,
  activeVideoDimensions,
  patchWorkflow,
}: EnhanceFormBindingParams) {
  const algorithmBindings = createEnhanceAlgorithmBindings({ workflow, checkResult })
  const viewBindings = createEnhanceViewBindings({
    workflow,
    activeVideoDimensions,
    currentInterpolationAlgorithm: algorithmBindings.currentInterpolationAlgorithm,
    currentSuperResolutionAlgorithm: algorithmBindings.currentSuperResolutionAlgorithm,
  })
  const effectBindings = createEnhanceEffectBindings({
    workflow,
    checkResult,
    effectiveSuperResolutionNumFrames: viewBindings.effectiveSuperResolutionNumFrames,
    patchWorkflow,
  })
  const scalarBindings = createEnhanceScalarFieldBindings({ workflow, patchWorkflow })

  return reactive({
    interpolationOnnxModels: algorithmBindings.interpolationOnnxModels,
    superResolutionOnnxModels: algorithmBindings.superResolutionOnnxModels,
    interpolationAlgorithms: algorithmBindings.interpolationAlgorithms,
    superResolutionAlgorithms: algorithmBindings.superResolutionAlgorithms,
    interpolationModels: algorithmBindings.interpolationModels,
    isInterpolationOnnxBackend: algorithmBindings.isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend: algorithmBindings.isSuperResolutionOnnxBackend,
    currentInterpolationAlgorithm: algorithmBindings.currentInterpolationAlgorithm,
    interpolationModelDetails: viewBindings.interpolationModelDetails,
    interpolationOnnxModelDetails: viewBindings.interpolationOnnxModelDetails,
    superResolutionOnnxModelDetails: viewBindings.superResolutionOnnxModelDetails,
    currentInterpolationModelDetail: viewBindings.currentInterpolationModelDetail,
    currentInterpolationRuntimeDetail: viewBindings.currentInterpolationRuntimeDetail,
    interpolationRuntimeEstimate: viewBindings.interpolationRuntimeEstimate,
    interpolationMetricRows: viewBindings.interpolationMetricRows,
    superResolutionMetricRows: viewBindings.superResolutionMetricRows,
    combinedPeakVramBytes: viewBindings.combinedPeakVramBytes,
    combinedVramMetricRows: viewBindings.combinedVramMetricRows,
    isSuperResolutionInputFramesEditable: viewBindings.isSuperResolutionInputFramesEditable,
    superResolutionInputFramesLabel: viewBindings.superResolutionInputFramesLabel,
    superResolutionInputFramesHint: viewBindings.superResolutionInputFramesHint,
    superResolutionFixedWindowRows: viewBindings.superResolutionFixedWindowRows,
    isPaddleGanSuperResolution: viewBindings.isPaddleGanSuperResolution,
    ...effectBindings,
    ...scalarBindings,
  })
}
