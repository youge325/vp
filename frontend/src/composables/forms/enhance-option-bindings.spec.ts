import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { createEnhanceOptionBindings } from '@/composables/forms/enhance-option-bindings'
import { useEnvStore } from '@/stores/env'
import type { EnvironmentCheckResult, ModelVariantInfo } from '@/types/domain/env'

type EnhanceOptionForm = Parameters<typeof createEnhanceOptionBindings>[0]

const detail = (name: string, label: string): ModelVariantInfo => ({
  name,
  label,
  metrics: {
    analysisStatus: 'ok',
    analysisNotes: [],
  },
})

function makeEnv(): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: true, devices: ['NVIDIA GPU'], adapters: [], cudaAvailable: true },
    tensorBackends: { pytorch: true, paddle: true, onnx: true },
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda'], onnx: ['tensorrt', 'cuda'] },
    onnxRuntime: { available: true, providers: ['CUDAExecutionProvider'] },
    rifeModel: { available: true },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    animeProfiles: [],
  }
}

function makeForm(): EnhanceOptionForm {
  return reactive({
    interpolationBackend: 'pytorch',
    interpolationEngine: 'cuda',
    interpolationAlgorithm: 'rife',
    interpolationModel: '4.25',
    interpolationOnnxModel: '',
    interpolationAlgorithms: [
      { name: 'rife', tensorBackends: ['pytorch'], models: ['4.25'] },
    ],
    interpolationModels: ['4.25'],
    interpolationOnnxModels: [],
    interpolationModelDetails: [detail('4.25', 'RIFE 4.25')],
    interpolationOnnxModelDetails: [],
    fpsMode: 'multi',
    interpolationMulti: 2,
    superResolutionBackend: 'onnx',
    superResolutionEngine: 'cuda',
    superResolutionAlgorithm: 'placeholder',
    superResolutionOnnxModel: '',
    superResolutionScale: 2,
    superResolutionAlgorithms: [
      {
        name: 'placeholder',
        tensorBackends: ['onnx'],
        models: [],
        modelDetails: [detail('placeholder', 'ONNX SR')],
      },
    ],
    superResolutionOnnxModels: ['sr.onnx'],
    superResolutionOnnxModelDetails: [detail('sr.onnx', 'SR ONNX')],
    processOrder: 'super_resolution_then_interpolation',
    animeProfile: 'clean-lines',
    animeProfiles: ['clean-lines', 'line-art'],
  })
}

describe('enhance option bindings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-07-08T00:00:00Z',
    )
  })

  it('builds select options and ONNX empty-list view state', () => {
    const bindings = createEnhanceOptionBindings(makeForm())

    expect(bindings.backendOptions).toEqual([
      { value: 'pytorch', label: 'PyTorch' },
      { value: 'paddle', label: 'PaddlePaddle' },
      { value: 'onnx', label: 'ONNX Runtime' },
    ])
    expect(bindings.interpolationEngineOptions).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'tensorrt', label: 'TensorRT' },
    ])
    expect(bindings.interpolationAlgorithmOptions).toEqual([{ value: 'rife', label: 'rife' }])
    expect(bindings.interpolationModelOptions).toEqual([{ value: '4.25', label: '4.25' }])
    expect(bindings.interpolationOnnxOptions).toEqual([{ value: '', label: '未选择' }])
    expect(bindings.interpolationOnnxDisabled).toBe(true)
    expect(bindings.interpolationOnnxHint).toContain('models/interpolation')
    expect(bindings.superResolutionOnnxOptions).toEqual([
      { value: '', label: '未选择' },
      { value: 'sr.onnx', label: 'sr.onnx' },
    ])
    expect(bindings.animeProfileOptions).toEqual([
      { value: 'clean-lines', label: 'clean-lines' },
      { value: 'line-art', label: 'line-art' },
    ])
  })

  it('applies string select values through domain conversion setters', () => {
    const form = makeForm()
    const bindings = createEnhanceOptionBindings(form)

    bindings.setInterpolationBackend('onnx')
    bindings.setInterpolationEngine('tensorrt')
    bindings.setFpsMode('target')
    bindings.setInterpolationMulti('4')
    bindings.setSuperResolutionBackend('paddle')
    bindings.setSuperResolutionEngine('cuda')
    bindings.setSuperResolutionScale('4')
    bindings.setProcessOrder('frame_interpolation_then_super_resolution')
    bindings.setAnimeProfile('line-art')

    expect(form.interpolationBackend).toBe('onnx')
    expect(form.interpolationEngine).toBe('tensorrt')
    expect(form.fpsMode).toBe('target')
    expect(form.interpolationMulti).toBe(4)
    expect(form.superResolutionBackend).toBe('paddle')
    expect(form.superResolutionEngine).toBe('cuda')
    expect(form.superResolutionScale).toBe(4)
    expect(form.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(form.animeProfile).toBe('line-art')
  })
})
