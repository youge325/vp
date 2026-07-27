import { toNumberValue } from '@/services/preset/options'
import type { EnhanceOptionForm } from '@/composables/forms/enhance-option-state'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/protocol'

export function createEnhanceOptionSetters(form: EnhanceOptionForm) {
  function setInterpolationBackend(value: string): void {
    form.interpolationBackend = value as TensorBackend
  }

  function setInterpolationEngine(value: string): void {
    form.interpolationEngine = value as InferenceEngine
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
    form.fpsMode = value as FpsMode
  }

  function setInterpolationMulti(value: string): void {
    form.interpolationMulti = toNumberValue(value)
  }

  function setSuperResolutionBackend(value: string): void {
    form.superResolutionBackend = value as TensorBackend
  }

  function setSuperResolutionEngine(value: string): void {
    form.superResolutionEngine = value as InferenceEngine
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
    form.processOrder = value as ProcessOrder
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
