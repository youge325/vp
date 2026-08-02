import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import App from '@/App.vue'
import { useTaskStore } from '@/stores/task'

vi.mock('vue-router', () => ({
  RouterView: { template: '<div />' },
  useRoute: () => ({ meta: { module: { key: 'home', title: '主页' } } }),
}))

vi.mock('@/composables/app/useBootstrap', () => ({
  useBootstrap: vi.fn(),
}))

vi.mock('@/composables/app/useEnvironmentChecker', () => ({
  useEnvironmentChecker: () => ({ checkEnvironment: vi.fn() }),
}))

vi.mock('@/composables/selectors/useOperationIssue', () => ({
  useOperationIssue: () => ({ value: null }),
}))

function mountApp() {
  return shallowMount(App, {
    global: {
      stubs: {
        IssueBanner: true,
        RouterView: true,
        StepRail: true,
      },
    },
  })
}

describe('App task status projection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('projects the single batch phase for running, paused and idle labels', async () => {
    const wrapper = mountApp()
    const status = () => wrapper.get('.status-pill').text()
    expect(status()).toBe('idle')

    const taskStore = useTaskStore()
    taskStore.dispatchBatch({ type: 'started', ids: ['item'] })
    taskStore.dispatchBatch({ type: 'queue-advanced', currentId: 'item', remaining: [] })
    await nextTick()
    expect(status()).toBe('running')

    taskStore.dispatchBatch({ type: 'control-requested', kind: 'pause' })
    taskStore.dispatchBatch({ type: 'control-succeeded', kind: 'pause' })
    await nextTick()
    expect(status()).toBe('paused')

    taskStore.dispatchBatch({ type: 'item-finalized' })
    await nextTick()
    expect(status()).toBe('idle')
  })
})
