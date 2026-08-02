import { describe, expect, it } from 'vitest'

import {
  FPS_MODE_OPTIONS,
  MULTI_OPTIONS,
  PROCESS_ORDER_OPTIONS,
  buildAlgorithmOptions,
  buildBackendOptions,
  buildEnhanceOptions,
  buildEngineOptions,
  buildModelOptions,
  buildOnnxModelOptions,
} from '@/services/preset/enhance-options'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/protocol'
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
  it('builds backend and engine options with shared GPU labels', () => {
    expect(buildBackendOptions(['pytorch', 'onnx'])).toEqual([
      { value: 'pytorch', label: 'PyTorch' },
      { value: 'onnx', label: 'ONNX Runtime' },
    ])
    expect(buildEngineOptions(['cuda', 'tensorrt', 'dcu'])).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'tensorrt', label: 'TensorRT' },
      { value: 'dcu', label: 'DCU' },
    ])
  })

  it('builds model and ONNX options with metric-aware labels and empty placeholders', () => {
    expect(buildModelOptions(['4.25', 'lite'], [detail('4.25')])).toEqual([
      { value: '4.25', label: '4.25 · 5.67M' },
      { value: 'lite', label: 'lite' },
    ])
    expect(buildOnnxModelOptions(['rife.onnx'], [detail('rife.onnx', null)])).toEqual([
      { value: '', label: '未选择' },
      { value: 'rife.onnx', label: 'rife.onnx' },
    ])
  })

  it('builds algorithm options without view-local mapping rules', () => {
    const algorithms: AlgorithmInfo[] = [
      createAlgorithmInfo({ name: 'rife', tensorBackends: ['pytorch'], models: ['4.25'] }),
      createAlgorithmInfo({
        name: 'ppmsvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        modelDetails: [detail('x2', 2_000_000), detail('x4')],
      }),
    ]

    expect(buildAlgorithmOptions(algorithms, 'name')).toEqual([
      { value: 'rife', label: 'rife' },
      { value: 'ppmsvsr', label: 'ppmsvsr' },
    ])
    expect(buildAlgorithmOptions(algorithms, 'modelMetrics')).toEqual([
      { value: 'rife', label: 'rife' },
      { value: 'ppmsvsr', label: 'ppmsvsr · 2.00M' },
    ])
    expect(buildAlgorithmOptions(algorithms, 'modelMetrics', 'x4')).toEqual([
      { value: 'rife', label: 'rife' },
      { value: 'ppmsvsr', label: 'ppmsvsr · 5.67M' },
    ])
  })

  it('exposes stable static options', () => {
    expect(FPS_MODE_OPTIONS).toEqual([
      { value: 'target', label: '目标 FPS' },
      { value: 'multi', label: '倍率' },
    ])
    expect(MULTI_OPTIONS).toEqual([
      { value: '2', label: '2x' },
      { value: '4', label: '4x' },
    ])
    expect(PROCESS_ORDER_OPTIONS).toEqual([
      { value: 'super_resolution_then_interpolation', label: '先超分后补帧' },
      { value: 'frame_interpolation_then_super_resolution', label: '先补帧后超分' },
    ])
  })

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

    expect(options.backendOptions.map(({ value }) => value)).toEqual([
      'pytorch',
      'paddle',
      'onnx',
    ])
    expect(options.interpolationEngineOptions.map(({ value }) => value)).toEqual([
      'cuda',
      'tensorrt',
    ])
    expect(options.interpolationAlgorithmOptions).toEqual([{ value: 'rife', label: 'rife' }])
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
  })
})
