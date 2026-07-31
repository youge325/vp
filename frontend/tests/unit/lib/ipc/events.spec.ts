import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  TASK_EVENT_NAMES,
  type ResumeStatusPayload,
  type TaskEventName,
} from '@/types/protocol'
import type { TaskEventListeners } from '@/lib/ipc/events'

const { listenMock, unlistenMock } = vi.hoisted(() => ({
  listenMock: vi.fn(),
  unlistenMock: vi.fn(),
}))

vi.mock('@tauri-apps/api/event', () => ({
  listen: listenMock,
}))

import { listenTaskEvents } from '@/lib/ipc/events'

function listeners(): TaskEventListeners {
  return Object.fromEntries(
    Object.values(TASK_EVENT_NAMES).map((name) => [name, vi.fn()]),
  ) as unknown as TaskEventListeners
}

describe('listenTaskEvents', () => {
  beforeEach(() => {
    listenMock.mockReset()
    unlistenMock.mockReset()
    listenMock.mockResolvedValue(unlistenMock)
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {},
    })
  })

  it('subscribes every generated task event exactly once', async () => {
    const handlers = listeners()

    const detach = await listenTaskEvents(handlers)

    expect(listenMock.mock.calls.map(([name]) => name)).toEqual(Object.values(TASK_EVENT_NAMES))
    detach()
    expect(unlistenMock).toHaveBeenCalledTimes(Object.values(TASK_EVENT_NAMES).length)
  })

  it('routes a generated event payload to its keyed listener', async () => {
    const handlers = listeners()
    await listenTaskEvents(handlers)
    const name: TaskEventName = TASK_EVENT_NAMES.TaskResumeStatus
    const call = listenMock.mock.calls.find(([eventName]) => eventName === name)
    const callback = call?.[1] as ((event: { payload: ResumeStatusPayload }) => void) | undefined
    const payload: ResumeStatusPayload = {
      resumed: true,
      completedChunks: 2,
      completedOutputFrames: 20,
      startSourceFrame: 10,
      totalOutputFrames: 100,
    }

    callback?.({ payload })

    expect(handlers[name]).toHaveBeenCalledWith(payload)
  })

  it('returns a no-op listener outside the Tauri runtime', async () => {
    Reflect.deleteProperty(window, '__TAURI_INTERNALS__')

    const detach = await listenTaskEvents(listeners())

    expect(listenMock).not.toHaveBeenCalled()
    expect(detach()).toBeUndefined()
  })
})
