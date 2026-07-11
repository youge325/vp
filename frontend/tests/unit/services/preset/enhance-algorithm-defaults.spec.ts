import { describe, expect, it } from 'vitest'

import {
  pickDefaultInterpolationAlgorithm,
  pickDefaultSuperResolutionAlgorithm,
} from '@/services/preset/enhance-algorithm-defaults'
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

describe('enhance algorithm defaults', () => {
  it('selects backend-compatible interpolation and super-resolution algorithms', () => {
    const checkResult = env({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
        { name: 'paddle-rife', tensorBackends: ['paddle'], models: ['paddle-v1'] },
      ],
      superResolutionAlgorithms: [
        { name: 'placeholder', tensorBackends: ['onnx'], models: [] },
        { name: 'paddle-sr', tensorBackends: ['paddle'], models: [] },
      ],
    })

    expect(pickDefaultInterpolationAlgorithm(checkResult, 'paddle')).toBe('paddle-rife')
    expect(pickDefaultSuperResolutionAlgorithm(checkResult, 'paddle')).toBe('paddle-sr')
  })

  it('keeps legacy hard-coded algorithm defaults when environment metadata is missing', () => {
    expect(pickDefaultInterpolationAlgorithm(null, 'onnx')).toBe('rife')
    expect(pickDefaultSuperResolutionAlgorithm(null, 'onnx')).toBe('placeholder')
  })
})
