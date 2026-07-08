import { describe, expect, it } from 'vitest'

import { pickDefaultEngine, pickDefaultInterpolationEngine } from './enhance-engine-defaults'
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

describe('enhance engine defaults', () => {
  it('selects the first backend engine for general enhance workflows', () => {
    expect(pickDefaultEngine(env({ tensorEngines: { onnx: ['tensorrt', 'cuda'] } }), 'onnx')).toBe('tensorrt')
    expect(pickDefaultEngine(null, 'onnx')).toBeUndefined()
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
    expect(pickDefaultInterpolationEngine(null, 'pytorch')).toBeUndefined()
  })
})
