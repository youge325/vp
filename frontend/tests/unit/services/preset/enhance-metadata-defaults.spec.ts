import { describe, expect, it } from 'vitest'

import { pickDefaultInterpolationModel } from '@/services/preset/enhance-metadata-defaults'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function env(
  overrides: Parameters<typeof createEnvironmentResult>[0] = {},
): EnvironmentCheckResult {
  return createEnvironmentResult(overrides)
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

  it('uses bootstrap metadata defaults when environment metadata is missing', () => {
    expect(pickDefaultInterpolationModel(null, 'missing')).toBe('4.25')
  })
})
