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

  it('setIssue and setChecking/setBootstrapping flip independent fields', () => {
    const store = useEnvStore()
    store.setIssue({ code: 'missing_ffmpeg', message: 'no ffmpeg' })
    store.setChecking(true)
    store.setBootstrapping(true)

    expect(store.env.issue?.code).toBe('missing_ffmpeg')
    expect(store.env.isChecking).toBe(true)
    expect(store.env.isBootstrapping).toBe(true)

    store.setIssue(null)
    store.setChecking(false)
    expect(store.env.issue).toBeNull()
    expect(store.env.isChecking).toBe(false)
    expect(store.env.isBootstrapping).toBe(true) // still set
  })

  it('does not expose the relocated operationIssue surface', () => {
    const store = useEnvStore()
    expect('operationIssue' in store).toBe(false)
    expect('setOperationIssue' in store).toBe(false)
  })

  // Phase 16 — 锁住 setCheckResult 已下线。生产路径全走 setCheckPayload
  // (一次性写入 result + source + 时间戳),独立 setCheckResult 是 Phase
  // 16 前的 dead mutator。
  it('does not expose setCheckResult after Phase 16', () => {
    const store = useEnvStore()
    expect('setCheckResult' in store).toBe(false)
  })
})
