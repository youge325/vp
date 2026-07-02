import { beforeEach, describe, expect, it, vi } from 'vitest'

const { invokeMock } = vi.hoisted(() => ({
  invokeMock: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: invokeMock,
}))

import { envIpc } from './env'

function installTauriRuntime(): void {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    configurable: true,
    value: {},
  })
}

describe('envIpc', () => {
  beforeEach(() => {
    invokeMock.mockReset()
    invokeMock.mockResolvedValue({ result: {}, source: 'probe', checkedAt: '2026-06-30T00:00:00Z' })
    installTauriRuntime()
  })

  it('passes check_environment forceRefresh as camelCase', async () => {
    await envIpc.check(true)

    expect(invokeMock).toHaveBeenCalledWith('check_environment', {
      forceRefresh: true,
    })
  })

  it('uses a non-forced check by default', async () => {
    await envIpc.check()

    expect(invokeMock).toHaveBeenCalledWith('check_environment', {
      forceRefresh: false,
    })
  })
})
