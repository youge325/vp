import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createDeferred } from '../../fixtures/deferred'
import { createEnvironmentPayload } from '../../fixtures/environment'
import type { EnvironmentCheckPayload } from '@/types/protocol'

const mocks = vi.hoisted(() => ({
  check: vi.fn<(forceRefresh: boolean) => Promise<EnvironmentCheckPayload>>(),
}))

vi.mock('@/lib/ipc/endpoints/env', () => ({
  envIpc: { check: mocks.check },
}))

import { useEnvironmentChecker } from '@/composables/app/useEnvironmentChecker'
import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'

describe('useEnvironmentChecker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mocks.check.mockReset()
  })

  it('owns the complete successful check transition without clearing other scopes', async () => {
    const payload = createEnvironmentPayload()
    mocks.check.mockResolvedValue(payload)
    const issueStore = useIssueStore()
    issueStore.setIssue('preset', { code: 'persistence_failed', message: 'preset failed', details: null })
    issueStore.setIssue('environment', { code: 'process_failed', message: 'stale', details: null })

    const { checkEnvironment } = useEnvironmentChecker()
    await checkEnvironment({ forceRefresh: false })

    expect(mocks.check).toHaveBeenCalledWith(false)
    expect(useEnvStore().env.lastProbeAt).toBe(payload.checkedAt)
    expect(useEnvStore().env.isChecking).toBe(false)
    expect(issueStore.getIssue('environment')).toBeNull()
    expect(issueStore.getIssue('preset')?.message).toBe('preset failed')
  })

  it('normalizes a failed check into the environment scope only', async () => {
    mocks.check.mockRejectedValue(new Error('probe failed'))
    const issueStore = useIssueStore()
    issueStore.setIssue('task', { code: 'process_failed', message: 'task failed', details: null })

    const { checkEnvironment } = useEnvironmentChecker()
    await checkEnvironment()

    expect(issueStore.getIssue('environment')?.message).toBe('probe failed')
    expect(issueStore.getIssue('task')?.message).toBe('task failed')
    expect(useEnvStore().env.isChecking).toBe(false)
  })

  it('prevents an older concurrent check from overwriting the latest result', async () => {
    const stale = createDeferred<EnvironmentCheckPayload>()
    const latest = createEnvironmentPayload(undefined, { checkedAt: '2026-08-02T08:00:00Z' })
    mocks.check.mockReturnValueOnce(stale.promise).mockResolvedValueOnce(latest)
    const { checkEnvironment } = useEnvironmentChecker()

    const staleRun = checkEnvironment()
    await checkEnvironment()
    stale.resolve(createEnvironmentPayload(undefined, { checkedAt: '2026-01-01T00:00:00Z' }))
    await staleRun

    expect(useEnvStore().env.lastProbeAt).toBe(latest.checkedAt)
  })

  it('does not commit after its owner generation becomes inactive', async () => {
    const pending = createDeferred<EnvironmentCheckPayload>()
    mocks.check.mockReturnValueOnce(pending.promise)
    let active = true
    const { checkEnvironment } = useEnvironmentChecker()

    const run = checkEnvironment({ isActive: () => active })
    active = false
    pending.resolve(createEnvironmentPayload())
    await run

    expect(useEnvStore().env.checkResult).toBeNull()
    expect(useIssueStore().getIssue('environment')).toBeNull()
  })
})
