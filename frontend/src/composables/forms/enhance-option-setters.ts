import {
  toFpsMode,
  toInferenceEngine,
  toProcessOrder,
  toTensorBackend,
} from '@/services/preset/enhance-options'
import { toNumberValue } from '@/services/preset/options'
import type { EnhanceOptionForm } from '@/composables/forms/enhance-option-state'

export function createEnhanceOptionSetters(form: EnhanceOptionForm) {
  function setInterpolationBackend(value: string): void {
    form.interpolationBackend = toTensorBackend(value)
  }

  function setInterpolationEngine(value: string): void {
    form.interpolationEngine = toInferenceEngine(value)
  }

  function setInterpolationAlgorithm(value: string): void {
    form.interpolationAlgorithm = value
  }

  function setInterpolationModel(value: string): void {
    form.interpolationModel = value
  }

  function setInterpolationOnnxModel(value: string): void {
    form.interpolationOnnxModel = value
  }

  function setFpsMode(value: string): void {
    form.fpsMode = toFpsMode(value)
  }

  function setInterpolationMulti(value: string): void {
    form.interpolationMulti = toNumberValue(value)
  }

  function setSuperResolutionBackend(value: string): void {
    form.superResolutionBackend = toTensorBackend(value)
  }

  function setSuperResolutionEngine(value: string): void {
    form.superResolutionEngine = toInferenceEngine(value)
  }

  function setSuperResolutionAlgorithm(value: string): void {
    form.superResolutionAlgorithm = value
  }

  function setSuperResolutionOnnxModel(value: string): void {
    form.superResolutionOnnxModel = value
  }

  function setSuperResolutionScale(value: string): void {
    form.superResolutionScale = toNumberValue(value)
  }

  function setProcessOrder(value: string): void {
    form.processOrder = toProcessOrder(value)
  }

  return {
    setInterpolationBackend,
    setInterpolationEngine,
    setInterpolationAlgorithm,
    setInterpolationModel,
    setInterpolationOnnxModel,
    setFpsMode,
    setInterpolationMulti,
    setSuperResolutionBackend,
    setSuperResolutionEngine,
    setSuperResolutionAlgorithm,
    setSuperResolutionOnnxModel,
    setSuperResolutionScale,
    setProcessOrder,
  }
}
