import type { ComputedRef } from 'vue'
import { createDraftEditor } from '@/composables/forms/lens'
import {
  applyInterpolationAlgorithmSelection,
  applyInterpolationBackendSelection,
  applyInterpolationEnabled,
  applySuperResolutionAlgorithmSelection,
  applySuperResolutionBackendSelection,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from '@/services/preset/enhance-workflow'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export interface EnhanceEffectBindingParams {
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
      applyInterpolationBackendSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applySuperResolutionBackendSelection(c, value, checkResult.value)
    }),
  )
  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      applyInterpolationAlgorithmSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchWorkflow((c) => {
      applySuperResolutionAlgorithmSelection(c, value, checkResult.value)
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
