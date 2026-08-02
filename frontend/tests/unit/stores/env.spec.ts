import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useEnvStore } from '@/stores/env'
import type { EnvironmentCheckPayload, EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../fixtures/environment'

const sampleResult: EnvironmentCheckResult = createEnvironmentResult()

describe('useEnvStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('setCheckPayload stores the probe timestamp without write-only local state', () => {
    const store = useEnvStore()
    const payload: EnvironmentCheckPayload = {
      result: sampleResult,
      source: 'cache',
      checkedAt: '2026-05-01T00:00:00Z',
    }
    store.setCheckPayload(payload)

    expect(store.env.checkResult).toEqual(sampleResult)
    expect(store.env.checkSource).toBe('cache')
    expect(store.env.lastProbeAt).toBe('2026-05-01T00:00:00Z')
  })

  it('checking and bootstrapping remain independent lifecycle fields', () => {
    const store = useEnvStore()
    store.setChecking(true)
    store.setBootstrapping(true)

    expect(store.env.isChecking).toBe(true)
    expect(store.env.isBootstrapping).toBe(true)

    store.setChecking(false)
    expect(store.env.isChecking).toBe(false)
    expect(store.env.isBootstrapping).toBe(true) // still set
  })
})
