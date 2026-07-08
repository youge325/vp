import { computed, type ComputedRef } from 'vue'

import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export interface EnhanceAlgorithmBindingParams {
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

  const animeProfiles = computed(() => checkResult.value?.animeProfiles ?? [])
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
    animeProfiles,
    interpolationModels: interpolation.models,
    isOnnxBackend: isInterpolationOnnxBackend,
    isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend,
    currentInterpolationAlgorithm: interpolation.current,
    currentSuperResolutionAlgorithm,
  }
}
