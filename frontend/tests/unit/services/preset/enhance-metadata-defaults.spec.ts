import { describe, expect, it } from 'vitest'

import { pickDefaultInterpolationModel } from '@/services/preset/enhance-metadata-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function env(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return {
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: [], paddle: [], onnx: [] },
    backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    runtimeMode: 'external',
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
  })
})
