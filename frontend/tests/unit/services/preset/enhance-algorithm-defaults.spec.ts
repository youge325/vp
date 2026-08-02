import { describe, expect, it } from 'vitest'

import {
  pickDefaultInterpolationAlgorithm,
  pickDefaultSuperResolutionAlgorithm,
} from '@/services/preset/enhance-algorithm-defaults'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function env(
  overrides: Parameters<typeof createEnvironmentResult>[0] = {},
): EnvironmentCheckResult {
  return createEnvironmentResult(overrides)
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

  it('uses bootstrap algorithm defaults when environment metadata is missing', () => {
    expect(pickDefaultInterpolationAlgorithm(null, 'onnx')).toBe('rife')
    expect(pickDefaultSuperResolutionAlgorithm(null, 'pytorch')).toBe('real-rawvsr-basicvsr')
  })
})
