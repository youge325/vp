import { describe, expect, it } from 'vitest'

import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
} from './enhance-onnx-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

const env: EnvironmentCheckResult = {
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: [],
    encoderProfiles: [],
    decoderProfiles: [],
  },
  gpu: { available: false, devices: [], adapters: [] },
  tensorBackends: {},
  tensorEngines: {},
  onnxRuntime: { available: false, providers: [] },
  rifeModel: { available: false },
  interpolationAlgorithms: [
    { name: 'rife', tensorBackends: ['onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
  ],
  superResolutionAlgorithms: [
    { name: 'sr', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'] },
  ],
}

describe('enhance ONNX defaults', () => {
  it('seeds fallback ONNX models only when the current value is empty', () => {
    expect(fallbackInterpolationOnnxModel(env, 'rife', '')).toBe('rife.onnx')
    expect(fallbackInterpolationOnnxModel(env, 'rife', 'custom.onnx')).toBe('custom.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', '')).toBe('sr.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', 'custom-sr.onnx')).toBe('custom-sr.onnx')
  })
})
