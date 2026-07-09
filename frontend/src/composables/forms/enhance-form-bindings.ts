import { reactive, type ComputedRef } from 'vue'
import { createEnhanceAlgorithmBindings } from '@/composables/forms/enhance-algorithm-bindings'
import { createEnhanceFieldBindings } from '@/composables/forms/enhance-field-bindings'
import { createEnhanceViewBindings } from '@/composables/forms/enhance-view-bindings'
import type { VideoDimensions } from '@/types/view/model-metrics'
import type { EnvironmentCheckResult } from '@/types/domain/env'
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
  const fieldBindings = createEnhanceFieldBindings({
    workflow,
    checkResult,
    effectiveSuperResolutionNumFrames: viewBindings.effectiveSuperResolutionNumFrames,
    patchWorkflow,
  })

  return reactive({
    ...algorithmBindings,
    ...viewBindings,
    ...fieldBindings,
  })
}
