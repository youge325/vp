import { beforeEach, describe, expect, it, vi } from 'vitest'

const { invokeMock } = vi.hoisted(() => ({
  invokeMock: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: invokeMock,
}))

import { mediaIpc } from './media'

function installTauriRuntime(): void {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    configurable: true,
    value: {},
  })
}

function sampleVideoInfo() {
  return {
    type: 'info',
    fps: 24,
    frames: 120,
    duration: 5,
    width: 1920,
    height: 1080,
    hasAudio: true,
    videoCodec: 'h264',
  }
}

describe('mediaIpc', () => {
  beforeEach(() => {
    invokeMock.mockReset()
    invokeMock.mockResolvedValue(sampleVideoInfo())
    installTauriRuntime()
  })

  it('passes inspect_video input path using the Tauri camelCase argument name', async () => {
    await mediaIpc.inspect('D:/clip.mp4')

    expect(invokeMock).toHaveBeenCalledWith('inspect_video', {
      inputPath: 'D:/clip.mp4',
    })
  })

  it('passes pick_inputs without an argument object', async () => {
    await mediaIpc.pickInputs()

    expect(invokeMock).toHaveBeenCalledWith('pick_inputs', undefined)
  })
})
