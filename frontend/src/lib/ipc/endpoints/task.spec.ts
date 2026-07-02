import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TaskRequest } from '@/types/protocol'

const { invokeMock } = vi.hoisted(() => ({
  invokeMock: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: invokeMock,
}))

import { taskIpc } from './task'

function installTauriRuntime(): void {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    configurable: true,
    value: {},
  })
}

describe('taskIpc', () => {
  beforeEach(() => {
    invokeMock.mockReset()
    invokeMock.mockResolvedValue(undefined)
    installTauriRuntime()
  })

  it('passes start_task request payload', async () => {
    const request = { inputPath: 'D:/in.mp4' } as unknown as TaskRequest

    await taskIpc.start(request)

    expect(invokeMock).toHaveBeenCalledWith('start_task', {
      request,
    })
  })

  it('passes check_resume_state request payload', async () => {
    const request = { inputPath: 'D:/in.mp4' } as unknown as TaskRequest

    await taskIpc.checkResume(request)

    expect(invokeMock).toHaveBeenCalledWith('check_resume_state', {
      request,
    })
  })

  it('passes cancel_task without an argument object', async () => {
    await taskIpc.cancel()

    expect(invokeMock).toHaveBeenCalledWith('cancel_task', undefined)
  })

  it('passes pause and resume through control_task kind payloads', async () => {
    await taskIpc.pause()
    await taskIpc.resume()

    expect(invokeMock).toHaveBeenNthCalledWith(1, 'control_task', {
      kind: 'pause',
    })
    expect(invokeMock).toHaveBeenNthCalledWith(2, 'control_task', {
      kind: 'resume',
    })
  })

  it('passes open_output_location path payload', async () => {
    await taskIpc.openOutputLocation('D:/out/result.mp4')

    expect(invokeMock).toHaveBeenCalledWith('open_output_location', {
      path: 'D:/out/result.mp4',
    })
  })
})
