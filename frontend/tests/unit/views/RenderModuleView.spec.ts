import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RenderModuleView from '@/views/RenderModuleView.vue'

const orchestrator = vi.hoisted(() => ({
  batch: {
    phase: 'idle' as 'idle' | 'running' | 'paused' | 'cancelling',
    queue: [] as string[],
    currentId: null as string | null,
    controlPending: null as 'pause' | 'resume' | 'cancel' | null,
  },
  pendingConflict: null,
  canStartBatch: true,
  cannotStartReason: null,
  startBatch: vi.fn(),
  pauseCurrentTask: vi.fn(),
  resumeCurrentTask: vi.fn(),
  interruptBatch: vi.fn(),
  resolveConflict: vi.fn(),
}))

vi.mock('@/composables/app/useTaskOrchestrator', () => ({
  useTaskOrchestrator: () => orchestrator,
}))

vi.mock('@/composables/selectors/useOperationIssue', () => ({
  useOperationIssue: () => null,
}))

function mountView() {
  return shallowMount(RenderModuleView, {
    global: {
      stubs: {
        IssueBanner: true,
        ResumeConflictDialog: true,
        TaskConsole: true,
      },
    },
  })
}

describe('RenderModuleView batch phase controls', () => {
  beforeEach(() => {
    orchestrator.batch.phase = 'idle'
    orchestrator.batch.controlPending = null
    vi.clearAllMocks()
  })

  it.each([
    ['idle', '暂停队列', '中断批次', true],
    ['running', '暂停队列', '中断批次', false],
    ['paused', '继续队列', '中断批次', false],
    ['cancelling', '暂停队列', '中断中...', true],
  ] as const)('renders %s controls from the batch phase', (phase, pauseLabel, cancelLabel, disabled) => {
    orchestrator.batch.phase = phase
    const wrapper = mountView()
    const pause = wrapper.get('.ghost-button')
    const cancel = wrapper.get('.danger-button')

    expect(pause.text()).toBe(pauseLabel)
    expect(cancel.text()).toBe(cancelLabel)
    expect(pause.attributes('disabled') !== undefined).toBe(disabled)
    expect(cancel.attributes('disabled') !== undefined).toBe(disabled)
  })

  it('routes the paused action to resume and the running action to pause', async () => {
    orchestrator.batch.phase = 'paused'
    await mountView().get('.ghost-button').trigger('click')
    expect(orchestrator.resumeCurrentTask).toHaveBeenCalledOnce()

    orchestrator.batch.phase = 'running'
    await mountView().get('.ghost-button').trigger('click')
    expect(orchestrator.pauseCurrentTask).toHaveBeenCalledOnce()
  })
})
