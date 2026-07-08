import { describe, expect, it } from 'vitest'

import {
  pickDefaultAnimeProfile,
  pickDefaultEngine,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationEngine,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-default-pickers'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function env(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
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

describe('enhance default pickers', () => {
  it('selects backend-compatible algorithms and metadata fallbacks', () => {
    const checkResult = env({
      tensorEngines: { onnx: ['tensorrt', 'cuda'], paddle: ['cuda'] },
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
        { name: 'paddle-rife', tensorBackends: ['paddle'], models: ['paddle-v1'] },
      ],
      superResolutionAlgorithms: [
        { name: 'placeholder', tensorBackends: ['onnx'], models: [] },
        { name: 'paddle-sr', tensorBackends: ['paddle'], models: [] },
      ],
      animeProfiles: ['clean-lines'],
    })

    expect(pickDefaultEngine(checkResult, 'onnx')).toBe('tensorrt')
    expect(pickDefaultInterpolationAlgorithm(checkResult, 'paddle')).toBe('paddle-rife')
    expect(pickDefaultInterpolationModel(checkResult, 'paddle-rife')).toBe('paddle-v1')
    expect(pickDefaultSuperResolutionAlgorithm(checkResult, 'paddle')).toBe('paddle-sr')
    expect(pickDefaultAnimeProfile(checkResult)).toBe('clean-lines')
  })

  it('keeps legacy hard-coded defaults when environment metadata is missing', () => {
    expect(pickDefaultEngine(null, 'onnx')).toBeUndefined()
    expect(pickDefaultInterpolationEngine(null, 'pytorch')).toBeUndefined()
    expect(pickDefaultInterpolationAlgorithm(null, 'onnx')).toBe('rife')
    expect(pickDefaultInterpolationModel(null, 'missing')).toBe('4.25')
    expect(pickDefaultSuperResolutionAlgorithm(null, 'onnx')).toBe('placeholder')
    expect(pickDefaultAnimeProfile(null)).toBe('clean-lines')
  })

  it('applies vendor-specific interpolation engine preferences', () => {
    const nvidia = env({
      gpu: { available: true, devices: ['RTX'], adapters: [{ name: 'RTX', vendor: 'nvidia', deviceType: 'discrete' }] },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'] },
    })
    const hygon = env({
      gpu: { available: true, devices: ['DCU'], adapters: [{ name: 'DCU', vendor: 'hygon', deviceType: 'discrete' }] },
      tensorEngines: { pytorch: ['cuda', 'dcu'] },
    })
    const generic = env({
      gpu: { available: true, devices: ['GPU'], adapters: [{ name: 'GPU', vendor: 'unknown', deviceType: 'discrete' }] },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'] },
    })

    expect(pickDefaultInterpolationEngine(nvidia, 'pytorch')).toBe('tensorrt')
    expect(pickDefaultInterpolationEngine(hygon, 'pytorch')).toBe('dcu')
    expect(pickDefaultInterpolationEngine(generic, 'pytorch')).toBe('cuda')
  })
})
