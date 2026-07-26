import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const unlistenMock = vi.hoisted(() => vi.fn())
const listenMock = vi.hoisted(() => vi.fn(async () => unlistenMock))

vi.mock('@/lib/ipc/events', () => ({
  listenTaskEvents: listenMock,
}))

vi.mock('@/lib/ipc/endpoints/task', () => ({
  taskIpc: {
    start: vi.fn(),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    checkResume: vi.fn(),
    openOutputLocation: vi.fn(),
  },
}))

import {
  attachTaskListeners,
  disposeRunner,
  getTaskRunner,
} from '@/composables/app/taskOrchestratorRuntime'

describe('taskOrchestratorRuntime', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listenMock.mockClear()
    unlistenMock.mockClear()
  })

  afterEach(() => {
    disposeRunner()
  })

  it('registers the IPC listener once across repeated attach calls', async () => {
    const runner = getTaskRunner()

    await attachTaskListeners()
    await attachTaskListeners()
    await attachTaskListeners()

    expect(listenMock).toHaveBeenCalledTimes(1)
    expect(listenMock).toHaveBeenCalledWith(runner)
  })

  it('disposes the listener and cached runner before the next mount cycle', async () => {
    const firstRunner = getTaskRunner()
    await attachTaskListeners()

    disposeRunner()

    expect(unlistenMock).toHaveBeenCalledTimes(1)
    const secondRunner = getTaskRunner()
    await attachTaskListeners()
    expect(secondRunner).not.toBe(firstRunner)
    expect(listenMock).toHaveBeenCalledTimes(2)
  })

  it('binds a fresh runner after Pinia is replaced', async () => {
    const firstRunner = getTaskRunner()
    await attachTaskListeners()

    disposeRunner()
    setActivePinia(createPinia())

    const secondRunner = getTaskRunner()
    await attachTaskListeners()
    expect(secondRunner).not.toBe(firstRunner)
    expect(listenMock).toHaveBeenCalledTimes(2)
  })
})
