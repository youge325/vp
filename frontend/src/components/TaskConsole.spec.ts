import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const taskStoreState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/task', () => ({
  useTaskStore: () => taskStoreState.current,
}))

import TaskConsole from '@/components/TaskConsole.vue'

function createStoreMock(logs: string[] = []) {
  return {
    consoleTaskItem: {
      taskState: {
        logs,
      },
    },
  }
}

describe('TaskConsole', () => {
  beforeEach(() => {
    taskStoreState.current = createStoreMock()
  })

  it('renders only terminal logs without the legacy progress header UI', () => {
    const wrapper = mount(TaskConsole)

    expect(wrapper.find('.task-console-head').exists()).toBe(false)
    expect(wrapper.find('.log-panel').exists()).toBe(true)
  })

  it('renders logs from store', () => {
    taskStoreState.current = createStoreMock(['line 1', 'line 2'])
    const wrapper = mount(TaskConsole)

    const lines = wrapper.findAll('.log-line')
    expect(lines.length).toBe(2)
    expect(lines[0].text()).toBe('line 1')
    expect(lines[1].text()).toBe('line 2')
  })
})
