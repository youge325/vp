import { describe, expect, it } from 'vitest'

import { pickDefaultAnimeProfile, pickDefaultInterpolationModel } from './enhance-metadata-defaults'
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
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    animeProfiles: [],
    ...overrides,
  } as EnvironmentCheckResult
}

describe('enhance metadata defaults', () => {
  it('selects the first interpolation model for the selected algorithm', () => {
    expect(pickDefaultInterpolationModel(env({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch'], models: ['4.25'] },
        { name: 'rife-fast', tensorBackends: ['pytorch'], models: ['4.26'] },
      ],
    }), 'rife-fast')).toBe('4.26')
  })

  it('keeps legacy metadata fallbacks when environment metadata is missing', () => {
    expect(pickDefaultInterpolationModel(null, 'missing')).toBe('4.25')
    expect(pickDefaultAnimeProfile(null)).toBe('clean-lines')
  })

  it('selects the first anime profile from environment metadata', () => {
    expect(pickDefaultAnimeProfile(env({ animeProfiles: ['line-art', 'clean-lines'] }))).toBe('line-art')
  })
})
