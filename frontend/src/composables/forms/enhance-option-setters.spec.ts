import { reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createEnhanceOptionSetters } from '@/composables/forms/enhance-option-setters'
import type { EnhanceOptionForm } from '@/composables/forms/enhance-option-bindings'

function makeForm(): EnhanceOptionForm {
  return reactive({
    interpolationBackend: 'pytorch',
    interpolationEngine: 'cuda',
    interpolationAlgorithm: 'rife',
    interpolationModel: '4.25',
    interpolationOnnxModel: '',
    interpolationAlgorithms: [],
    interpolationModels: [],
    interpolationOnnxModels: [],
    interpolationModelDetails: [],
    interpolationOnnxModelDetails: [],
    fpsMode: 'multi',
    interpolationMulti: 2,
    superResolutionBackend: 'onnx',
    superResolutionEngine: 'cuda',
    superResolutionAlgorithm: 'placeholder',
    superResolutionOnnxModel: '',
    superResolutionScale: 2,
    superResolutionAlgorithms: [],
    superResolutionOnnxModels: [],
    superResolutionOnnxModelDetails: [],
    processOrder: 'super_resolution_then_interpolation',
    animeProfile: 'clean-lines',
    animeProfiles: [],
  })
}

describe('enhance option setters', () => {
  it('applies string select values through domain conversion setters', () => {
    const form = makeForm()
    const setters = createEnhanceOptionSetters(form)

    setters.setInterpolationBackend('onnx')
    setters.setInterpolationEngine('tensorrt')
    setters.setInterpolationAlgorithm('rife-lite')
    setters.setInterpolationModel('lite')
    setters.setInterpolationOnnxModel('rife.onnx')
    setters.setFpsMode('target')
    setters.setInterpolationMulti('4')
    setters.setSuperResolutionBackend('paddle')
    setters.setSuperResolutionEngine('cuda')
    setters.setSuperResolutionAlgorithm('ppmsvsr')
    setters.setSuperResolutionOnnxModel('sr.onnx')
    setters.setSuperResolutionScale('4')
    setters.setProcessOrder('frame_interpolation_then_super_resolution')
    setters.setAnimeProfile('line-art')

    expect(form.interpolationBackend).toBe('onnx')
    expect(form.interpolationEngine).toBe('tensorrt')
    expect(form.interpolationAlgorithm).toBe('rife-lite')
    expect(form.interpolationModel).toBe('lite')
    expect(form.interpolationOnnxModel).toBe('rife.onnx')
    expect(form.fpsMode).toBe('target')
    expect(form.interpolationMulti).toBe(4)
    expect(form.superResolutionBackend).toBe('paddle')
    expect(form.superResolutionEngine).toBe('cuda')
    expect(form.superResolutionAlgorithm).toBe('ppmsvsr')
    expect(form.superResolutionOnnxModel).toBe('sr.onnx')
    expect(form.superResolutionScale).toBe(4)
    expect(form.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(form.animeProfile).toBe('line-art')
  })
})
