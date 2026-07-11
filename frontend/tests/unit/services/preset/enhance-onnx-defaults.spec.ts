import { describe, expect, it } from 'vitest'

import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
} from '@/services/preset/enhance-onnx-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

const env: EnvironmentCheckResult = {
  ffmpeg: {
    available: true,
    hwaccels: [],
    encoderProfiles: [],
    decoderProfiles: [],
  },
  gpu: { adapters: [] },
  tensorEngines: { pytorch: [], paddle: [], onnx: [] },
  backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
  interpolationAlgorithms: [
    { name: 'rife', tensorBackends: ['onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
  ],
  superResolutionAlgorithms: [
    { name: 'sr', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'] },
  ],
  runtimeMode: 'external',
}

describe('enhance ONNX defaults', () => {
  it('seeds fallback ONNX models only when the current value is empty', () => {
    expect(fallbackInterpolationOnnxModel(env, 'rife', '')).toBe('rife.onnx')
    expect(fallbackInterpolationOnnxModel(env, 'rife', 'custom.onnx')).toBe('custom.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', '')).toBe('sr.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', 'custom-sr.onnx')).toBe('custom-sr.onnx')
  })
})
