import { describe, expect, it } from 'vitest'

import { createFilterModelParamsPatch } from '@/services/filters/filter-params'

describe('createFilterModelParamsPatch', () => {
  it('updates a writable model without mutating its current step', () => {
    const source = { kind: 'sharpen' as const, enabled: true, params: { amount: 0.5 } }
    const model = { value: source }
    const patch = createFilterModelParamsPatch(model)

    patch((params) => {
      params.amount = 0.75
    })

    expect(source.params.amount).toBe(0.5)
    expect(model.value).toEqual({ kind: 'sharpen', enabled: true, params: { amount: 0.75 } })
  })
})
