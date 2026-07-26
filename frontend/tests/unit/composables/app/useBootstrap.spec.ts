import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  attachTaskListeners: vi.fn(async () => undefined),
  disposeRunner: vi.fn(),
  loadPersistedPreset: vi.fn(async () => undefined),
  startAutoSync: vi.fn(),
  recheckEnvironment: vi.fn(async () => undefined),
}))

vi.mock('@/composables/app/taskOrchestratorRuntime', () => ({
  attachTaskListeners: mocks.attachTaskListeners,
  disposeRunner: mocks.disposeRunner,
}))

vi.mock('@/composables/app/useEnvironmentChecker', () => ({
  useEnvironmentChecker: () => ({
    recheckEnvironment: mocks.recheckEnvironment,
  }),
}))

vi.mock('@/composables/app/usePresetSync', () => ({
  usePresetSync: () => ({
    loadPersistedPreset: mocks.loadPersistedPreset,
    startAutoSync: mocks.startAutoSync,
  }),
}))

import { useBootstrap } from '@/composables/app/useBootstrap'
import { useEnvStore } from '@/stores/env'
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
  })

  it('owns listener attachment and disposal around application startup', async () => {
    const wrapper = mount(BootstrapHost)
    await flushPromises()

    expect(mocks.attachTaskListeners).toHaveBeenCalledOnce()
    expect(mocks.loadPersistedPreset).toHaveBeenCalledOnce()
    expect(mocks.recheckEnvironment).toHaveBeenCalledWith(false)
    expect(mocks.startAutoSync).toHaveBeenCalledOnce()
    expect(mocks.attachTaskListeners.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.loadPersistedPreset.mock.invocationCallOrder[0])
    expect(mocks.loadPersistedPreset.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.recheckEnvironment.mock.invocationCallOrder[0])
    expect(mocks.recheckEnvironment.mock.invocationCallOrder[0])
      .toBeLessThan(mocks.startAutoSync.mock.invocationCallOrder[0])
    expect(useEnvStore().env.isBootstrapping).toBe(false)
    expect(usePresetStore().presetPersistenceReady).toBe(true)

    wrapper.unmount()
    expect(mocks.disposeRunner).toHaveBeenCalledOnce()
  })
})
