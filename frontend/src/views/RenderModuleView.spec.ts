import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const storeState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/workbench', () => ({
  useWorkbenchStore: () => storeState.current,
}))

import RenderModuleView from '@/views/RenderModuleView.vue'

function createStoreMock(overrides: Record<string, unknown> = {}) {
  return reactive({
    batch: {
      isRunning: false,
      isPaused: false,
      isCancelling: false,
    },
    canStartBatch: true,
    operationIssue: null,
    startBatch: vi.fn(),
    pauseCurrentTask: vi.fn(),
    resumeCurrentTask: vi.fn(),
    interruptBatch: vi.fn(),
    consoleTaskItem: null,
    ...overrides,
  })
}

function mountView() {
  return mount(RenderModuleView, {
    global: {
      stubs: {
        TaskConsole: true,
      },
    },
  })
}

describe('RenderModuleView', () => {
  it('renders start, pause, and interrupt buttons side by side', () => {
    storeState.current = createStoreMock()

    const wrapper = mountView()
    const buttons = wrapper.findAll('button')

    expect(buttons).toHaveLength(3)
    expect(buttons[0]?.text()).toBe('开始队列')
    expect(buttons[0]?.attributes('disabled')).toBeUndefined()
    expect(buttons[1]?.text()).toBe('暂停队列')
    expect(buttons[1]?.attributes('disabled')).toBeDefined()
    expect(buttons[2]?.text()).toBe('中断批次')
    expect(buttons[2]?.attributes('disabled')).toBeDefined()
  })

  it('forwards pause, resume, and interrupt interactions', async () => {
    const pauseCurrentTask = vi.fn()
    const resumeCurrentTask = vi.fn()
    const interruptBatch = vi.fn()
    storeState.current = createStoreMock({
      batch: {
        isRunning: true,
        isPaused: false,
        isCancelling: false,
      },
      canStartBatch: false,
      pauseCurrentTask,
      resumeCurrentTask,
      interruptBatch,
    })

    const wrapper = mountView()
    let buttons = wrapper.findAll('button')

    expect(buttons[0]?.attributes('disabled')).toBeDefined()
    expect(buttons[1]?.text()).toBe('暂停队列')
    expect(buttons[1]?.attributes('disabled')).toBeUndefined()
    expect(buttons[2]?.attributes('disabled')).toBeUndefined()

    await buttons[1]?.trigger('click')
    await buttons[2]?.trigger('click')

    expect(pauseCurrentTask).toHaveBeenCalledTimes(1)
    expect(interruptBatch).toHaveBeenCalledTimes(1)

    storeState.current.batch.isPaused = true
    await wrapper.vm.$nextTick()
    buttons = wrapper.findAll('button')
    expect(buttons[1]?.text()).toBe('继续队列')

    await buttons[1]?.trigger('click')
    expect(resumeCurrentTask).toHaveBeenCalledTimes(1)
  })

  it('disables task controls while an interrupt is pending', () => {
    storeState.current = createStoreMock({
      batch: {
        isRunning: true,
        isPaused: false,
        isCancelling: true,
      },
      canStartBatch: false,
    })

    const wrapper = mountView()
    const buttons = wrapper.findAll('button')

    expect(buttons[1]?.attributes('disabled')).toBeDefined()
    expect(buttons[2]?.text()).toBe('中断中...')
    expect(buttons[2]?.attributes('disabled')).toBeDefined()
  })
})
