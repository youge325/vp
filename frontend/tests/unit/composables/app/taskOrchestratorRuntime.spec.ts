import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createDeferred } from '../../fixtures/deferred'

const unlistenMock = vi.hoisted(() => vi.fn())
const listenMock = vi.hoisted(() => vi.fn(async (_listeners: unknown, _onError: unknown) => unlistenMock))

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
import { useIssueStore } from '@/stores/issue'
import type { TaskEventName } from '@/types/protocol'

describe('taskOrchestratorRuntime', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listenMock.mockReset()
    listenMock.mockResolvedValue(unlistenMock)
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
    const listeners = listenMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect(listeners['task-progress']).toEqual(expect.any(Function))
    expect(listeners['task-progress']).not.toBe(runner.onProgress)
    expect(listeners['task-resume-status']).toEqual(expect.any(Function))
  })

  it('projects listener failures into the global task issue', async () => {
    await attachTaskListeners()
    const onListenerError = listenMock.mock.calls[0]?.[1] as
      | ((name: TaskEventName, error: unknown) => void)
      | undefined

    onListenerError?.('task-completed', new Error('completion handler failed'))

    expect(useIssueStore().getIssue('task')).toEqual({
      code: 'process_failed',
      message: 'completion handler failed',
      details: null,
    })
  })

  it('ignores listener failures from a disposed runtime generation', async () => {
    await attachTaskListeners()
    const obsoleteErrorHandler = listenMock.mock.calls[0]?.[1] as
      | ((name: TaskEventName, error: unknown) => void)
      | undefined

    disposeRunner()
    setActivePinia(createPinia())
    await attachTaskListeners()
    obsoleteErrorHandler?.('task-completed', new Error('obsolete failure'))

    expect(useIssueStore().getIssue('task')).toBeNull()
  })

  it('shares one in-flight attachment across concurrent callers', async () => {
    const pending = createDeferred<typeof unlistenMock>()
    listenMock.mockReturnValueOnce(pending.promise)

    const first = attachTaskListeners()
    const second = attachTaskListeners()
    const third = attachTaskListeners()

    expect(first).toBe(second)
    expect(second).toBe(third)
    expect(listenMock).toHaveBeenCalledOnce()

    pending.resolve(unlistenMock)
    await Promise.all([first, second, third])
    expect(listenMock).toHaveBeenCalledOnce()
  })

  it('detaches a late listener when disposal wins the attachment race', async () => {
    const lateUnlisten = vi.fn()
    const pending = createDeferred<typeof lateUnlisten>()
    listenMock.mockReturnValueOnce(pending.promise)
    const firstRunner = getTaskRunner()

    const attaching = attachTaskListeners()
    disposeRunner()
    pending.resolve(lateUnlisten)
    await attaching

    expect(lateUnlisten).toHaveBeenCalledOnce()
    expect(getTaskRunner()).not.toBe(firstRunner)
  })

  it('ignores callbacks captured by an attachment after its generation is disposed', async () => {
    const pending = createDeferred<typeof unlistenMock>()
    listenMock.mockReturnValueOnce(pending.promise)
    const runner = getTaskRunner()
    const onLog = vi.spyOn(runner, 'onLog')

    const attaching = attachTaskListeners()
    const obsoleteListeners = listenMock.mock.calls[0]?.[0] as {
      'task-log': (payload: { message: string }) => void | Promise<void>
    }
    disposeRunner()
    await obsoleteListeners['task-log']({ message: 'late event' })
    pending.resolve(unlistenMock)
    await attaching

    expect(onLog).not.toHaveBeenCalled()
  })

  it('does not leak listeners across 100 attach/dispose races', async () => {
    for (let generation = 0; generation < 100; generation += 1) {
      const lateUnlisten = vi.fn()
      const pending = createDeferred<typeof lateUnlisten>()
      listenMock.mockReturnValueOnce(pending.promise)

      const first = attachTaskListeners()
      const second = attachTaskListeners()
      expect(second).toBe(first)

      disposeRunner()
      pending.resolve(lateUnlisten)
      await Promise.all([first, second])
      expect(lateUnlisten).toHaveBeenCalledOnce()
    }

    expect(listenMock).toHaveBeenCalledTimes(100)
  })

  it('keeps a newer attachment when an obsolete generation finishes last', async () => {
    const obsoleteUnlisten = vi.fn()
    const currentUnlisten = vi.fn()
    const obsolete = createDeferred<typeof obsoleteUnlisten>()
    const current = createDeferred<typeof currentUnlisten>()
    listenMock
      .mockReturnValueOnce(obsolete.promise)
      .mockReturnValueOnce(current.promise)

    const obsoleteAttach = attachTaskListeners()
    disposeRunner()
    const currentAttach = attachTaskListeners()

    current.resolve(currentUnlisten)
    await currentAttach
    obsolete.resolve(obsoleteUnlisten)
    await obsoleteAttach

    expect(obsoleteUnlisten).toHaveBeenCalledOnce()
    expect(currentUnlisten).not.toHaveBeenCalled()
    disposeRunner()
    expect(currentUnlisten).toHaveBeenCalledOnce()
  })

  it('clears a failed attachment so the next call can retry', async () => {
    const failure = new Error('listen failed')
    listenMock.mockRejectedValueOnce(failure)

    await expect(attachTaskListeners()).rejects.toBe(failure)
    await expect(attachTaskListeners()).resolves.toBeUndefined()

    expect(listenMock).toHaveBeenCalledTimes(2)
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
