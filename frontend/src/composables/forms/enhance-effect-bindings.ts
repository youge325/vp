import type { ComputedRef } from 'vue'
import { createDraftEditor } from '@/composables/forms/lens'
import {
  applyInterpolationEnabled,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from '@/services/preset/enhance-workflow'
import {
  applyInterpolationAlgorithmSelectionDefaults,
  applyInterpolationBackendSelectionDefaults,
  applySuperResolutionAlgorithmSelectionDefaults,
  applySuperResolutionBackendSelectionDefaults,
} from '@/services/preset/enhance-workflow-selection'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { TensorBackend } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'

interface EnhanceEffectBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  effectiveSuperResolutionNumFrames: ComputedRef<number>
  patchWorkflow: (mutator: (workflow: WorkflowConfig) => void) => void
}

export function createEnhanceEffectBindings({
  workflow,
  checkResult,
  effectiveSuperResolutionNumFrames,
  patchWorkflow,
}: EnhanceEffectBindingParams) {
  const { effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflow,
  )

  const interpolationEnabled = effect<boolean>(
    () => workflow.value.interpolation.enabled,
    (value) => patchWorkflow((c) => {
      applyInterpolationEnabled(c, value, checkResult.value)
    }),
  )
  const superResolutionEnabled = effect<boolean>(
    () => workflow.value.superResolution.enabled,
    (value) => patchWorkflow((c) => {
      applySuperResolutionEnabled(c, value, checkResult.value)
    }),
  )
  const superResolutionScale = effect<number>(
    () => workflow.value.superResolution.scaleFactor,
    (value) => patchWorkflow((c) => {
      applySuperResolutionScale(c, value, checkResult.value)
    }),
  )
  const superResolutionNumFrames = effect<number>(
    () => effectiveSuperResolutionNumFrames.value,
    (value) => patchWorkflow((c) => {
      applySuperResolutionNumFrames(c, value, checkResult.value)
    }),
  )
  const interpolationBackend = effect<TensorBackend>(
    () => workflow.value.interpolation.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applyInterpolationBackendSelectionDefaults(c, value, checkResult.value)
    }),
  )
  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applySuperResolutionBackendSelectionDefaults(c, value, checkResult.value)
    }),
  )
  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      applyInterpolationAlgorithmSelectionDefaults(c, value, checkResult.value)
    }),
  )
  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchWorkflow((c) => {
      applySuperResolutionAlgorithmSelectionDefaults(c, value, checkResult.value)
    }),
  )

  return {
    interpolationEnabled,
    interpolationBackend,
    interpolationAlgorithm,
    superResolutionEnabled,
    superResolutionBackend,
    superResolutionScale,
    superResolutionAlgorithm,
    superResolutionNumFrames,
  }
}
