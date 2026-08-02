import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useIssueStore } from '@/stores/issue'
import { TASK_ERROR_CODES } from '@/types/protocol'
import type { TaskErrorPayload } from '@/types/protocol'

const allScopes = ['input', 'encode', 'task', 'preset', 'environment'] as const

function makeError(message = 'something went wrong'): TaskErrorPayload {
  return { code: TASK_ERROR_CODES.ProcessFailed, message, details: null }
}

describe('useIssueStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no issue in any scope', () => {
    const store = useIssueStore()
    for (const scope of allScopes) {
      expect(store.getIssue(scope)).toBeNull()
    }
  })

  it('retains independent errors for every scope', () => {
    const store = useIssueStore()
    for (const scope of allScopes) {
      store.setIssue(scope, makeError(`failure in ${scope}`))
    }
    for (const scope of allScopes) {
      expect(store.getIssue(scope)?.message).toBe(`failure in ${scope}`)
    }
  })

  it('clears only the requested scope', () => {
    const store = useIssueStore()
    store.setIssue('input', makeError('input failure'))
    store.setIssue('environment', makeError('environment failure'))

    store.clearIssue('environment')

    expect(store.getIssue('environment')).toBeNull()
    expect(store.getIssue('input')?.message).toBe('input failure')
  })

  it('clears every scope only when explicitly reset without a scope', () => {
    const store = useIssueStore()
    store.setIssue('preset', makeError('preset failure'))
    store.setIssue('task', makeError('task failure'))

    store.clearIssue()

    expect(store.getIssue('preset')).toBeNull()
    expect(store.getIssue('task')).toBeNull()
  })
})
