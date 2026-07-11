import { describe, expect, it } from 'vitest'

import { pickDefaultEngine, pickDefaultInterpolationEngine } from '@/services/preset/enhance-engine-defaults'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function env(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return createEnvironmentResult(overrides)
}

describe('enhance engine defaults', () => {
  it('selects the first backend engine for general enhance workflows', () => {
    expect(pickDefaultEngine(env({ tensorEngines: { pytorch: [], paddle: [], onnx: ['tensorrt', 'cuda'] } }), 'onnx')).toBe('tensorrt')
    expect(pickDefaultEngine(null, 'onnx')).toBeUndefined()
  })

  it('applies vendor-specific interpolation engine preferences', () => {
    const nvidia = env({
      gpu: { adapters: [{ name: 'RTX', vendor: 'nvidia' }] },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: [], onnx: [] },
    })
    const hygon = env({
      gpu: { adapters: [{ name: 'DCU', vendor: 'hygon' }] },
      tensorEngines: { pytorch: ['cuda', 'dcu'], paddle: [], onnx: [] },
    })
    const generic = env({
      gpu: { adapters: [{ name: 'GPU', vendor: 'other' }] },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: [], onnx: [] },
    })

    expect(pickDefaultInterpolationEngine(nvidia, 'pytorch')).toBe('tensorrt')
    expect(pickDefaultInterpolationEngine(hygon, 'pytorch')).toBe('dcu')
    expect(pickDefaultInterpolationEngine(generic, 'pytorch')).toBe('cuda')
    expect(pickDefaultInterpolationEngine(null, 'pytorch')).toBeUndefined()
  })
})
