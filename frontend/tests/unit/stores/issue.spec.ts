import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useIssueStore } from '@/stores/issue'
import { TASK_ERROR_CODES } from '@/types/protocol'
import type { TaskErrorPayload } from '@/types/protocol'

// Banner-surface store split out of ``useMediaStore``.
// Cover every scope so a future regression that drops or mis-routes
// a scope tag fails loudly here instead of surfacing as a silently
// missing banner in the UI.

const allScopes = ['input', 'encode', 'task', 'preset'] as const

function makeError(message = 'something went wrong'): TaskErrorPayload {
  return { code: TASK_ERROR_CODES.ProcessFailed, message, details: null }
}

describe('useIssueStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts idle with no active issue', () => {
    const store = useIssueStore()
    expect(store.operationIssue).toBeNull()
    for (const scope of allScopes) {
      expect(store.getIssue(scope)).toBeNull()
    }
  })

  it('setIssue / getIssue round-trip on every scope', () => {
    const store = useIssueStore()
    for (const scope of allScopes) {
      const error = makeError(`failure in ${scope}`)
      store.setIssue(scope, error)
      expect(store.operationIssue?.scope).toBe(scope)
      // Pinia wraps stored values in reactive proxies, so reference
      // equality fails even though the contents match. Use structural
      // equality here — what matters is that the surface reads back
      // what was written, not that the literal object survived.
      expect(store.operationIssue?.error).toEqual(error)
      expect(store.getIssue(scope)).toEqual(error)
    }
  })

  it('clearIssue without a scope clears any active issue', () => {
    const store = useIssueStore()
    store.setIssue('encode', makeError())
    store.clearIssue()
    expect(store.operationIssue).toBeNull()
  })

  it('clearIssue with a matching scope clears the active issue', () => {
    const store = useIssueStore()
    store.setIssue('preset', makeError())
    store.clearIssue('preset')
    expect(store.operationIssue).toBeNull()
  })

  it('clearIssue with a different scope leaves the issue intact', () => {
    // Critical invariant: a success path in scope A must not silently
    // wipe an unrelated banner currently visible for scope B.
    const store = useIssueStore()
    const error = makeError('input issue')
    store.setIssue('input', error)
    store.clearIssue('encode')
    expect(store.operationIssue?.scope).toBe('input')
    expect(store.operationIssue?.error).toEqual(error)
  })

  it('getIssue returns null for a non-matching scope even when an issue is set', () => {
    const store = useIssueStore()
    store.setIssue('task', makeError())
    expect(store.getIssue('input')).toBeNull()
    expect(store.getIssue('encode')).toBeNull()
    expect(store.getIssue('preset')).toBeNull()
    expect(store.getIssue('task')).not.toBeNull()
  })

  it('setIssue overwrites a prior issue from a different scope', () => {
    // We only model a single active banner at any time; switching
    // scopes is a deliberate replacement, not a queue.
    const store = useIssueStore()
    store.setIssue('input', makeError('first'))
    store.setIssue('task', makeError('second'))
    expect(store.operationIssue?.scope).toBe('task')
    expect(store.operationIssue?.error.message).toBe('second')
    expect(store.getIssue('input')).toBeNull()
  })
})
