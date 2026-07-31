import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createDeferred } from '../../fixtures/deferred'
import { createEnvironmentPayload } from '../../fixtures/environment'
import type { EnvironmentCheckPayload } from '@/types/protocol'

const mocks = vi.hoisted(() => ({
  attachTaskListeners: vi.fn(async () => undefined),
  disposeRunner: vi.fn(),
  loadPersistedPreset: vi.fn(async () => undefined),
  startAutoSync: vi.fn(),
  disposePresetSync: vi.fn(),
  requestEnvironmentCheck: vi.fn<() => Promise<EnvironmentCheckPayload>>(),
}))

vi.mock('@/composables/app/taskOrchestratorRuntime', () => ({
  attachTaskListeners: mocks.attachTaskListeners,
  disposeRunner: mocks.disposeRunner,
}))

vi.mock('@/composables/app/useEnvironmentChecker', () => ({
  requestEnvironmentCheck: mocks.requestEnvironmentCheck,
}))

vi.mock('@/composables/app/usePresetSync', () => ({
  usePresetSync: () => ({
    loadPersistedPreset: mocks.loadPersistedPreset,
    startAutoSync: mocks.startAutoSync,
    dispose: mocks.disposePresetSync,
  }),
}))

import { useBootstrap } from '@/composables/app/useBootstrap'
import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'

const BootstrapHost = defineComponent({
  setup() {
    useBootstrap()
    return () => null
  },
})

describe('useBootstrap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.attachTaskListeners.mockResolvedValue(undefined)
    mocks.loadPersistedPreset.mockResolvedValue(undefined)
    mocks.requestEnvironmentCheck.mockResolvedValue(createEnvironmentPayload())
  })

  it('owns listener attachment and disposal around application startup', async () => {
    const wrapper = mount(BootstrapHost)
    await flushPromises()

    expect(mocks.attachTaskListeners).toHaveBeenCalledOnce()
    expect(mocks.loadPersistedPreset).toHaveBeenCalledOnce()
    expect(mocks.requestEnvironmentCheck).toHaveBeenCalledWith(false)
    expect(mocks.startAutoSync).toHaveBeenCalledOnce()
    expect(mocks.attachTaskListeners.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.loadPersistedPreset.mock.invocationCallOrder[0])
    expect(mocks.loadPersistedPreset.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.requestEnvironmentCheck.mock.invocationCallOrder[0])
    expect(mocks.requestEnvironmentCheck.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.startAutoSync.mock.invocationCallOrder[0])
    expect(useEnvStore().env.isBootstrapping).toBe(false)
    expect(usePresetStore().presetPersistenceReady).toBe(true)

    wrapper.unmount()
    expect(mocks.disposeRunner).toHaveBeenCalledOnce()
    expect(mocks.disposePresetSync).toHaveBeenCalledOnce()
  })

  it('does not continue startup when unmounted during listener attachment', async () => {
    const attachment = createDeferred<undefined>()
    mocks.attachTaskListeners.mockReturnValueOnce(attachment.promise)
    const wrapper = mount(BootstrapHost)

    expect(mocks.attachTaskListeners).toHaveBeenCalledOnce()
    wrapper.unmount()
    attachment.resolve(undefined)
    await flushPromises()

    expect(mocks.loadPersistedPreset).not.toHaveBeenCalled()
    expect(mocks.requestEnvironmentCheck).not.toHaveBeenCalled()
    expect(mocks.startAutoSync).not.toHaveBeenCalled()
    expect(mocks.disposePresetSync).toHaveBeenCalledOnce()
  })

  it('surfaces listener attachment failures and keeps persistence unavailable', async () => {
    const failure = new Error('event registration failed')
    mocks.attachTaskListeners.mockRejectedValueOnce(failure)

    const wrapper = mount(BootstrapHost)
    await flushPromises()

    expect(useIssueStore().getIssue('task')).toEqual({
      code: 'process_failed',
      message: failure.message,
      details: null,
    })
    expect(usePresetStore().presetPersistenceReady).toBe(false)
    expect(useEnvStore().env.isBootstrapping).toBe(false)
    expect(mocks.loadPersistedPreset).not.toHaveBeenCalled()
    expect(mocks.requestEnvironmentCheck).not.toHaveBeenCalled()
    expect(mocks.startAutoSync).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('does not probe or start autosync when unmounted during preset loading', async () => {
    const presetLoad = createDeferred<undefined>()
    mocks.loadPersistedPreset.mockReturnValueOnce(presetLoad.promise)
    const wrapper = mount(BootstrapHost)
    await flushPromises()

    expect(mocks.loadPersistedPreset).toHaveBeenCalledOnce()
    wrapper.unmount()
    presetLoad.resolve(undefined)
    await flushPromises()

    expect(mocks.requestEnvironmentCheck).not.toHaveBeenCalled()
    expect(mocks.startAutoSync).not.toHaveBeenCalled()
  })

  it('does not start autosync when unmounted during the environment probe', async () => {
    const environmentCheck = createDeferred<EnvironmentCheckPayload>()
    mocks.requestEnvironmentCheck.mockReturnValueOnce(environmentCheck.promise)
    const wrapper = mount(BootstrapHost)
    await flushPromises()

    expect(mocks.requestEnvironmentCheck).toHaveBeenCalledOnce()
    wrapper.unmount()
    environmentCheck.resolve(createEnvironmentPayload())
    await flushPromises()

    expect(mocks.startAutoSync).not.toHaveBeenCalled()
    expect(useEnvStore().env.isBootstrapping).toBe(false)
    expect(usePresetStore().presetPersistenceReady).toBe(false)
  })

  it('does not let a stale probe overwrite a newer mount generation', async () => {
    const staleCheck = createDeferred<EnvironmentCheckPayload>()
    const freshPayload = createEnvironmentPayload(undefined, {
      checkedAt: '2026-07-31T12:00:00Z',
    })
    mocks.requestEnvironmentCheck
      .mockReturnValueOnce(staleCheck.promise)
      .mockResolvedValueOnce(freshPayload)

    const staleWrapper = mount(BootstrapHost)
    await flushPromises()
    staleWrapper.unmount()

    const freshWrapper = mount(BootstrapHost)
    await flushPromises()
    expect(useEnvStore().env.lastProbeAt).toBe(freshPayload.checkedAt)

    staleCheck.resolve(createEnvironmentPayload(undefined, {
      checkedAt: '2026-01-01T00:00:00Z',
    }))
    await flushPromises()
    expect(useEnvStore().env.lastProbeAt).toBe(freshPayload.checkedAt)

    freshWrapper.unmount()
  })
})
