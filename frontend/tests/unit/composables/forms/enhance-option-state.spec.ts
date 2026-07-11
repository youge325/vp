import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { createEnhanceOptionState } from '@/composables/forms/enhance-option-state'
import { useEnvStore } from '@/stores/env'
import type { EnvironmentCheckResult, ModelVariantInfo } from '@/types/domain/env'

type EnhanceOptionForm = Parameters<typeof createEnhanceOptionState>[0]

const detail = (name: string): ModelVariantInfo => ({
  name,
  label: name,
  metrics: {
    analysisStatus: 'ok',
    analysisNotes: [],
  },
})

function makeEnv(): EnvironmentCheckResult {
  return {
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda'], onnx: ['tensorrt', 'cuda'] },
    backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    runtimeMode: 'bundled',
  }
}

function makeForm(): EnhanceOptionForm {
  return reactive({
    interpolationBackend: 'pytorch',
    interpolationEngine: 'cuda',
    interpolationAlgorithm: 'rife',
    interpolationModel: '4.25',
    interpolationOnnxModel: '',
    interpolationAlgorithms: [{ name: 'rife', tensorBackends: ['pytorch'], models: ['4.25'] }],
    interpolationModels: ['4.25'],
    interpolationOnnxModels: [],
    interpolationModelDetails: [detail('4.25')],
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
        modelDetails: [detail('placeholder')],
      },
    ],
    superResolutionOnnxModels: ['sr.onnx'],
    superResolutionOnnxModelDetails: [detail('sr.onnx')],
    processOrder: 'super_resolution_then_interpolation',
  })
}

describe('enhance option state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-07-08T00:00:00Z',
    )
  })

  it('builds enhance select view state from form and GPU capabilities', () => {
    const state = createEnhanceOptionState(makeForm())

    expect(state.backendOptions.value).toEqual([
      { value: 'pytorch', label: 'PyTorch' },
      { value: 'paddle', label: 'PaddlePaddle' },
      { value: 'onnx', label: 'ONNX Runtime' },
    ])
    expect(state.interpolationEngineOptions.value).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'tensorrt', label: 'TensorRT' },
    ])
    expect(state.interpolationAlgorithmOptions.value).toEqual([{ value: 'rife', label: 'rife' }])
    expect(state.interpolationOnnxOptions.value).toEqual([{ value: '', label: '未选择' }])
    expect(state.interpolationOnnxDisabled.value).toBe(true)
    expect(state.interpolationOnnxHint.value).toContain('models/interpolation')
    expect(state.superResolutionOnnxOptions.value).toEqual([
      { value: '', label: '未选择' },
      { value: 'sr.onnx', label: 'sr.onnx' },
    ])
  })
})
