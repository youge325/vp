import { reactive } from 'vue'

import { createEnhanceOptionSetters } from '@/composables/forms/enhance-option-setters'
import { createEnhanceOptionState } from '@/composables/forms/enhance-option-state'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'

export interface EnhanceOptionForm {
  interpolationBackend: TensorBackend
  interpolationEngine: InferenceEngine
  interpolationAlgorithm: string
  interpolationModel: string
  interpolationOnnxModel: string
  interpolationAlgorithms: AlgorithmInfo[]
  interpolationModels: string[]
  interpolationOnnxModels: string[]
  interpolationModelDetails: ModelVariantInfo[]
  interpolationOnnxModelDetails: ModelVariantInfo[]
  fpsMode: FpsMode
  interpolationMulti: number

  superResolutionBackend: TensorBackend
  superResolutionEngine: InferenceEngine
  superResolutionAlgorithm: string
  superResolutionOnnxModel: string
  superResolutionScale: number
  superResolutionAlgorithms: AlgorithmInfo[]
  superResolutionOnnxModels: string[]
  superResolutionOnnxModelDetails: ModelVariantInfo[]

  processOrder: ProcessOrder
  animeProfile: string
  animeProfiles: string[]
}

export function createEnhanceOptionBindings(form: EnhanceOptionForm) {
  return reactive({
    ...createEnhanceOptionState(form),
    ...createEnhanceOptionSetters(form),
  })
}
