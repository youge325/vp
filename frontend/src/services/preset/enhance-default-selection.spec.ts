import { describe, expect, it } from 'vitest'

import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  pickDefaultAnimeProfile,
  pickDefaultEngine,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-default-selection'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return {
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
    ...overrides,
  } as EnvironmentCheckResult
}

describe('enhance default selection rules', () => {
  it('selects backend-compatible defaults before falling back to the first algorithm', () => {
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
        { name: 'paddle-rife', tensorBackends: ['paddle'], models: ['v1'] },
      ],
      superResolutionAlgorithms: [
        { name: 'placeholder', tensorBackends: ['onnx'], models: [] },
        { name: 'paddle-sr', tensorBackends: ['paddle'], models: [] },
      ],
    })

    expect(pickDefaultInterpolationAlgorithm(env, 'paddle')).toBe('paddle-rife')
    expect(pickDefaultInterpolationModel(env, 'paddle-rife')).toBe('v1')
    expect(pickDefaultSuperResolutionAlgorithm(env, 'paddle')).toBe('paddle-sr')
    expect(pickDefaultInterpolationAlgorithm(env, 'pytorch')).toBe('rife')
  })

  it('keeps existing hard-coded fallback values when environment metadata is missing', () => {
    expect(pickDefaultEngine(null, 'onnx')).toBeUndefined()
    expect(pickDefaultInterpolationAlgorithm(null, 'onnx')).toBe('rife')
    expect(pickDefaultInterpolationModel(null, 'missing')).toBe('4.25')
    expect(pickDefaultSuperResolutionAlgorithm(null, 'onnx')).toBe('placeholder')
    expect(pickDefaultAnimeProfile(null)).toBe('clean-lines')
  })

  it('seeds ONNX models only when the current value is empty', () => {
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
      ],
      superResolutionAlgorithms: [
        { name: 'sr', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'] },
      ],
    })

    expect(fallbackInterpolationOnnxModel(env, 'rife', '')).toBe('rife.onnx')
    expect(fallbackInterpolationOnnxModel(env, 'rife', 'custom.onnx')).toBe('custom.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', '')).toBe('sr.onnx')
    expect(fallbackSuperResolutionOnnxModel(env, 'sr', 'custom-sr.onnx')).toBe('custom-sr.onnx')
  })
})
