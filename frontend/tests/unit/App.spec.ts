import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import App from '@/App.vue'
import { createMediaItem } from '@/services/media/factory'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createIdleTaskState } from '@/services/task/events'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'

vi.mock('vue-router', () => ({
  RouterView: { template: '<div />' },
  useRoute: () => ({ meta: { module: { key: 'home', title: '主页' } } }),
}))

vi.mock('@/composables/app/useBootstrap', () => ({
  useBootstrap: vi.fn(),
}))

vi.mock('@/composables/app/useEnvironmentChecker', () => ({
  useEnvironmentChecker: () => ({ recheckEnvironment: vi.fn() }),
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

  it('projects the current task context without a single-consumer composable', async () => {
    const wrapper = mountApp()
    const status = () => wrapper.get('.status-pill').text()
    expect(status()).toBe('idle')

    const item = createMediaItem('D:/video/input.mp4', createDefaultWorkbenchPreset(null))
    useMediaStore().appendItems([item])
    useTaskStore().setBatch({ currentId: item.id, isRunning: true })
    useMediaRunState().setTaskState(item.id, {
      ...createIdleTaskState(),
      status: 'running',
    })
    await nextTick()
    expect(status()).toBe('running')

    useTaskStore().setBatch({ isPaused: true })
    useMediaRunState().setTaskState(item.id, {
      ...createIdleTaskState(),
      status: 'paused',
    })
    await nextTick()
    expect(status()).toBe('paused')

    useTaskStore().setBatch({ currentId: 'missing-item', isRunning: false })
    await nextTick()
    expect(status()).toBe('idle')
  })
})
