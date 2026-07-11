import { reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import * as lensModule from '@/composables/forms/lens'
import { createDraftEditor } from '@/composables/forms/lens'

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

describe('createDraftEditor public surface', () => {
  it('keeps low-level field and effect helpers private to the draft editor module', () => {
    expect('fieldLens' in lensModule).toBe(false)
    expect('defineLens' in lensModule).toBe(false)
  })

  it('reads through to the current draft value', () => {
    const { state, patch } = createDraftStore()
    const { field } = createDraftEditor<Draft>(() => state.draft, patch)
    const count = field(
      (d) => d.count,
      (d, v: number) => { d.count = v },
    )
    expect(count.value).toBe(0)
  })

  it('writes through patcher so the draft is replaced reactively', () => {
    const { state, patch } = createDraftStore()
    const { field } = createDraftEditor<Draft>(() => state.draft, patch)
    const count = field(
      (d) => d.count,
      (d, v: number) => { d.count = v },
    )
    count.value = 42
    expect(state.draft.count).toBe(42)
    expect(count.value).toBe(42)
  })

  it('handles nested fields without cross-talk between lenses', () => {
    const { state, patch } = createDraftStore()
    const { field } = createDraftEditor<Draft>(() => state.draft, patch)
    const enabled = field(
      (d) => d.nested.enabled,
      (d, v: boolean) => { d.nested.enabled = v },
    )
    const label = field(
      (d) => d.nested.label,
      (d, v: string) => { d.nested.label = v },
    )
    enabled.value = true
    label.value = 'hello'
    expect(state.draft.nested).toEqual({ enabled: true, label: 'hello' })
  })

  it('effect() builds a writable computed from raw read/write closures', () => {
    // ``effect`` only re-evaluates when its tracked reactive deps change,
    // so the read closure must close over a reactive source (typical real
    // usage). Using a plain ``let`` would leave the computed stuck on its
    // cached initial value.
    const { state, patch } = createDraftStore()
    const { effect } = createDraftEditor<Draft>(() => state.draft, patch)
    const storage = ref('initial')
    const lens = effect(
      () => storage.value,
      (value: string) => { storage.value = value.toUpperCase() },
    )
    expect(lens.value).toBe('initial')
    lens.value = 'next'
    // The writer side-effect is preserved (useful for composite setters).
    expect(storage.value).toBe('NEXT')
    expect(lens.value).toBe('NEXT')
  })

  it('shares the prebound getRoot/patcher across multiple field calls', () => {
    const { state, patch } = createDraftStore()
    const { field } = createDraftEditor<Draft>(() => state.draft, patch)
    const count = field((d) => d.count, (d, v: number) => { d.count = v })
    const label = field((d) => d.nested.label, (d, v: string) => { d.nested.label = v })
    count.value = 7
    label.value = 'hi'
    expect(state.draft.count).toBe(7)
    expect(state.draft.nested.label).toBe('hi')
  })

  it('effect() builds a composite setter that can mutate multiple fields', () => {
    const { state, patch } = createDraftStore()
    const { effect } = createDraftEditor<Draft>(() => state.draft, patch)
    const toggle = effect<boolean>(
      () => state.draft.nested.enabled,
      (value) => patch((d) => {
        d.nested.enabled = value
        // Side effect: pin label to a derived value.
        d.nested.label = value ? 'ON' : 'OFF'
      }),
    )
    toggle.value = true
    expect(state.draft.nested).toEqual({ enabled: true, label: 'ON' })
    toggle.value = false
    expect(state.draft.nested).toEqual({ enabled: false, label: 'OFF' })
  })
})
