import { describe, expect, it } from 'vitest'

import {
  FPS_MODE_OPTIONS,
  MULTI_OPTIONS,
  PROCESS_ORDER_OPTIONS,
  buildAlgorithmOptions,
  buildBackendOptions,
  buildEngineOptions,
  buildModelOptions,
  buildOnnxModelOptions,
  toFpsMode,
  toInferenceEngine,
  toProcessOrder,
  toTensorBackend,
} from '@/services/preset/enhance-options'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/protocol'

function detail(name: string, parameterCount: number | null = 5670892): ModelVariantInfo {
  return {
    name,
    label: name,
    metrics: {
      parameterCount,
      analysisStatus: 'ok',
      analysisNotes: [],
    },
  }
}

describe('enhance option rules', () => {
  it('builds backend and engine options with shared GPU labels', () => {
    expect(buildBackendOptions(['pytorch', 'onnx'])).toEqual([
      { value: 'pytorch', label: 'PyTorch' },
      { value: 'onnx', label: 'ONNX Runtime' },
    ])
    expect(buildEngineOptions(['cuda', 'tensorrt', 'custom'])).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'tensorrt', label: 'TensorRT' },
      { value: 'custom', label: 'custom' },
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
      { name: 'rife', tensorBackends: ['pytorch'], models: ['4.25'] },
      { name: 'ppmsvsr', tensorBackends: ['paddle'], models: ['x4'], modelDetails: [detail('x4')] },
    ]

    expect(buildAlgorithmOptions(algorithms, 'name')).toEqual([
      { value: 'rife', label: 'rife' },
      { value: 'ppmsvsr', label: 'ppmsvsr' },
    ])
    expect(buildAlgorithmOptions(algorithms, 'modelMetrics')).toEqual([
      { value: 'rife', label: 'rife' },
      { value: 'ppmsvsr', label: 'ppmsvsr · 5.67M' },
    ])
  })

  it('exposes stable static options and typed select conversions', () => {
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

    expect(toTensorBackend('paddle')).toBe('paddle')
    expect(toInferenceEngine('tensorrt')).toBe('tensorrt')
    expect(toFpsMode('multi')).toBe('multi')
    expect(toProcessOrder('frame_interpolation_then_super_resolution')).toBe('frame_interpolation_then_super_resolution')
  })
})
