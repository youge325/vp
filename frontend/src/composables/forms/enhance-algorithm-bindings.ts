import { computed, type ComputedRef } from 'vue'

import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { TensorBackend } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'

interface EnhanceAlgorithmBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  checkResult: ComputedRef<EnvironmentCheckResult | null>
}

export function createEnhanceAlgorithmBindings({
  workflow,
  checkResult,
}: EnhanceAlgorithmBindingParams) {
  const interpolationBackendValue = computed(() => workflow.value.interpolation.tensorBackend as TensorBackend)
  const superResolutionBackendValue = computed(() => workflow.value.superResolution.tensorBackend as TensorBackend)

  const interpolation = createAlgorithmLens(
    computed(() => checkResult.value?.interpolationAlgorithms ?? []),
    computed(() => workflow.value.interpolation.algorithm),
    interpolationBackendValue,
  )

  const superResolutionAlgorithmSpecs = computed(() => checkResult.value?.superResolutionAlgorithms ?? [])
  const superResolution = createAlgorithmLens(
    superResolutionAlgorithmSpecs,
    computed(() => workflow.value.superResolution.algorithm),
    superResolutionBackendValue,
  )

  const isInterpolationOnnxBackend = computed(() => interpolationBackendValue.value === 'onnx')
  const isSuperResolutionOnnxBackend = computed(() => superResolutionBackendValue.value === 'onnx')
  const currentSuperResolutionAlgorithm = computed(() =>
    superResolutionAlgorithmSpecs.value.find((a) => a.name === workflow.value.superResolution.algorithm),
  )

  return {
    interpolationOnnxModels: interpolation.onnxModels,
    superResolutionOnnxModels: superResolution.onnxModels,
    interpolationAlgorithms: interpolation.algorithms,
    superResolutionAlgorithms: superResolution.algorithms,
    interpolationModels: interpolation.models,
    isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend,
    currentInterpolationAlgorithm: interpolation.current,
    currentSuperResolutionAlgorithm,
  }
}
