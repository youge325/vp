import { describe, expect, it, vi } from 'vitest'

import { createFilterModelParamsPatch, createFilterParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

describe('createFilterParamsPatch', () => {
  it('emits a cloned step without mutating the source', () => {
    const source: FilterStep = { kind: 'sharpen', enabled: true, params: { amount: 0.5 } }
    const emit = vi.fn()
    const patch = createFilterParamsPatch(() => source, emit)

    patch((params) => { params.amount = 0.8 })

    expect(source.params.amount).toBe(0.5)
    expect(emit).toHaveBeenCalledWith({ kind: 'sharpen', enabled: true, params: { amount: 0.8 } })
  })

  it('updates a writable model without mutating its current step', () => {
    const source = { kind: 'sharpen', enabled: true, params: { amount: 0.5 } } as const
    const model = { value: source }
    const patch = createFilterModelParamsPatch(model)

    patch((params) => {
      params.amount = 0.75
    })

    expect(source.params.amount).toBe(0.5)
    expect(model.value).toEqual({ kind: 'sharpen', enabled: true, params: { amount: 0.75 } })
  })
})
