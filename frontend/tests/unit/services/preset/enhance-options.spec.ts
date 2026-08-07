import { describe, expect, it } from 'vitest'

import { buildEnhanceOptions } from '@/services/preset/enhance-options'
import type { ModelVariantInfo } from '@/types/protocol'
import {
  createAlgorithmInfo,
  createEnvironmentResult,
  createModelVariantInfo,
} from '../../fixtures/environment'

function detail(name: string, parameterCount: number | null = 5670892): ModelVariantInfo {
  return createModelVariantInfo({
    name,
    label: name,
    metrics: {
      parameterCount,
      analysisStatus: 'ok',
      analysisNotes: [],
    },
  })
}

describe('enhance option rules', () => {
  it('builds one option snapshot from form inputs and a narrow environment snapshot', () => {
    const interpolationAlgorithm = createAlgorithmInfo({
      name: 'rife',
      tensorBackends: ['pytorch'],
      models: ['4.25'],
    })
    const superResolutionAlgorithm = createAlgorithmInfo({
      name: 'placeholder',
      tensorBackends: ['onnx'],
      models: [],
      scaleFactors: [2, 3, 4],
      modelDetails: [detail('placeholder')],
    })
    const options = buildEnhanceOptions({
      checkResult: createEnvironmentResult({
        tensorEngines: {
          pytorch: ['cuda', 'tensorrt'],
          paddle: ['cuda'],
          onnx: ['tensorrt', 'cuda'],
        },
      }),
      interpolationBackend: 'pytorch',
      superResolutionBackend: 'onnx',
      interpolationAlgorithms: [interpolationAlgorithm],
      interpolationModels: ['4.25'],
      interpolationOnnxModels: [],
      interpolationModelDetails: [detail('4.25')],
      interpolationOnnxModelDetails: [],
      superResolutionAlgorithms: [superResolutionAlgorithm],
      currentSuperResolutionAlgorithm: superResolutionAlgorithm,
      superResolutionScaleFactor: 3,
      superResolutionOnnxModels: ['sr.onnx'],
      superResolutionOnnxModelDetails: [detail('sr.onnx')],
    })

    expect(options.backendOptions).toEqual([
      { value: 'pytorch', label: 'PyTorch' },
      { value: 'paddle', label: 'PaddlePaddle' },
      { value: 'onnx', label: 'ONNX Runtime' },
    ])
    expect(options.interpolationEngineOptions.map(({ value }) => value)).toEqual([
      'cuda',
      'tensorrt',
    ])
    expect(options.interpolationAlgorithmOptions).toEqual([{ value: 'rife', label: 'rife' }])
    expect(options.interpolationModelOptions).toEqual([
      { value: '4.25', label: '4.25 · 5.67M' },
    ])
    expect(options.interpolationOnnxOptions).toEqual([{ value: '', label: '未选择' }])
    expect(options.interpolationOnnxDisabled).toBe(true)
    expect(options.interpolationOnnxHint).toContain('models/interpolation')
    expect(options.superResolutionOnnxOptions).toEqual([
      { value: '', label: '未选择' },
      { value: 'sr.onnx', label: 'sr.onnx · 5.67M' },
    ])
    expect(options.superResolutionScaleOptions).toEqual([
      { value: '2', label: '2x' },
      { value: '3', label: '3x' },
      { value: '4', label: '4x' },
    ])
    expect(options.fpsModeOptions).toEqual([
      { value: 'target', label: '目标 FPS' },
      { value: 'multi', label: '倍率' },
    ])
    expect(options.multiOptions).toEqual([
      { value: '2', label: '2x' },
      { value: '4', label: '4x' },
    ])
    expect(options.processOrderOptions).toEqual([
      { value: 'super_resolution_then_interpolation', label: '先超分后补帧' },
      { value: 'frame_interpolation_then_super_resolution', label: '先补帧后超分' },
    ])
  })
})
