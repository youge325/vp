import { describe, expect, it } from 'vitest'

import { finiteNumberOrNull } from '@/services/finite-number'

describe('finite-number', () => {
  it('preserves finite values and rejects absent or non-finite values', () => {
    expect(finiteNumberOrNull(0)).toBe(0)
    expect(finiteNumberOrNull(3.5)).toBe(3.5)
    expect(finiteNumberOrNull(null)).toBeNull()
    expect(finiteNumberOrNull(undefined)).toBeNull()
    expect(finiteNumberOrNull(Number.NaN)).toBeNull()
    expect(finiteNumberOrNull(Number.POSITIVE_INFINITY)).toBeNull()
  })
})
