import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const storeState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/workbench', () => ({
  useWorkbenchStore: () => storeState.current,
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
    storeState.current = createStoreMock()
  })

  it('renders only terminal logs without the legacy progress header UI', () => {
    const wrapper = mount(TaskConsole)

    expect(wrapper.find('.task-console-head').exists()).toBe(false)
    expect(wrapper.find('.progress-track').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('CLI')
    expect(wrapper.text()).not.toContain('0/0')
    expect(wrapper.text()).not.toContain('%')
  })

  it('renders CLI log lines inside the terminal panel', () => {
    storeState.current = createStoreMock(['[VP_PROGRESS] 25%', 'ffmpeg ready'])

    const wrapper = mount(TaskConsole)
    const lines = wrapper.findAll('.log-line')

    expect(lines).toHaveLength(2)
    expect(lines[0]?.text()).toContain('[VP_PROGRESS] 25%')
    expect(lines[1]?.text()).toContain('ffmpeg ready')
  })
})
