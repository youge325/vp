import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const envStoreState = vi.hoisted(() => ({ current: null as any }))
const taskStoreState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/env', () => ({
  useEnvStore: () => envStoreState.current,
}))

vi.mock('@/stores/task', () => ({
  useTaskStore: () => taskStoreState.current,
}))

import RenderModuleView from '@/views/RenderModuleView.vue'

function createEnvStoreMock(overrides: Record<string, unknown> = {}) {
  return reactive({
    operationIssue: null,
    ...overrides,
  })
}

function createTaskStoreMock(overrides: Record<string, unknown> = {}) {
  return reactive({
    batch: {
      isRunning: false,
      isPaused: false,
      isCancelling: false,
    },
    canStartBatch: true,
    startBatch: vi.fn(),
    pauseCurrentTask: vi.fn(),
    resumeCurrentTask: vi.fn(),
    interruptBatch: vi.fn(),
    consoleTaskItem: null,
    ...overrides,
  })
}

describe('RenderModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('disables buttons when batch is not running', () => {
    envStoreState.current = createEnvStoreMock()
    taskStoreState.current = createTaskStoreMock()
    const wrapper = mount(RenderModuleView)

    const startButton = wrapper.find('button.primary-button')
    const pauseButton = wrapper.findAll('button.ghost-button')[0]
    const interruptButton = wrapper.find('button.danger-button')

    expect(startButton.attributes('disabled')).toBeUndefined()
    expect(pauseButton.attributes('disabled')).toBeDefined()
    expect(interruptButton.attributes('disabled')).toBeDefined()
  })

  it('enables pause and interrupt when batch is running', () => {
    envStoreState.current = createEnvStoreMock()
    taskStoreState.current = createTaskStoreMock({
      batch: { isRunning: true, isPaused: false, isCancelling: false },
      canStartBatch: false,
    })
    const wrapper = mount(RenderModuleView)

    const startButton = wrapper.find('button.primary-button')
    const pauseButton = wrapper.findAll('button.ghost-button')[0]
    const interruptButton = wrapper.find('button.danger-button')

    expect(startButton.attributes('disabled')).toBeDefined()
    expect(pauseButton.attributes('disabled')).toBeUndefined()
    expect(interruptButton.attributes('disabled')).toBeUndefined()
  })

  it('calls startBatch when start button is clicked', async () => {
    const startBatch = vi.fn()
    envStoreState.current = createEnvStoreMock()
    taskStoreState.current = createTaskStoreMock({ startBatch })
    const wrapper = mount(RenderModuleView)

    await wrapper.find('button.primary-button').trigger('click')
    expect(startBatch).toHaveBeenCalled()
  })
})
