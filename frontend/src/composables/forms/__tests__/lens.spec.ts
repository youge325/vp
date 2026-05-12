import { reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { defineLens, fieldLens } from '../lens'

interface Draft {
  count: number
  nested: {
    enabled: boolean
    label: string
  }
}

function createDraftStore() {
  const state = reactive<{ draft: Draft }>({
    draft: { count: 0, nested: { enabled: false, label: '' } },
  })

  function patch(mutator: (draft: Draft) => void) {
    const next: Draft = JSON.parse(JSON.stringify(state.draft))
    mutator(next)
    state.draft = next
  }

  return { state, patch }
}

describe('fieldLens', () => {
  it('reads through to the current draft value', () => {
    const { state, patch } = createDraftStore()
    const count = fieldLens(
      () => state.draft,
      patch,
      (d) => d.count,
      (d, v: number) => { d.count = v },
    )
    expect(count.value).toBe(0)
  })

  it('writes through patcher so the draft is replaced reactively', () => {
    const { state, patch } = createDraftStore()
    const count = fieldLens(
      () => state.draft,
      patch,
      (d) => d.count,
      (d, v: number) => { d.count = v },
    )
    count.value = 42
    expect(state.draft.count).toBe(42)
    expect(count.value).toBe(42)
  })

  it('handles nested fields without cross-talk between lenses', () => {
    const { state, patch } = createDraftStore()
    const enabled = fieldLens(
      () => state.draft,
      patch,
      (d) => d.nested.enabled,
      (d, v: boolean) => { d.nested.enabled = v },
    )
    const label = fieldLens(
      () => state.draft,
      patch,
      (d) => d.nested.label,
      (d, v: string) => { d.nested.label = v },
    )
    enabled.value = true
    label.value = 'hello'
    expect(state.draft.nested).toEqual({ enabled: true, label: 'hello' })
  })
})

describe('defineLens', () => {
  it('builds a writable computed from raw read/write closures', () => {
    // ``defineLens`` only re-evaluates when its tracked reactive deps change,
    // so the read closure must close over a reactive source (typical real
    // usage). Using a plain ``let`` would leave the computed stuck on its
    // cached initial value.
    const storage = ref('initial')
    const lens = defineLens(
      () => storage.value,
      (value: string) => { storage.value = value.toUpperCase() },
    )
    expect(lens.value).toBe('initial')
    lens.value = 'next'
    // The writer side-effect is preserved (useful for composite setters).
    expect(storage.value).toBe('NEXT')
    expect(lens.value).toBe('NEXT')
  })
})
