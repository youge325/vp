import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorkbenchPreset } from '@/types/protocol'

const { invokeMock } = vi.hoisted(() => ({
  invokeMock: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: invokeMock,
}))

import { presetIpc } from '@/lib/ipc/endpoints/preset'

function installTauriRuntime(): void {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    configurable: true,
    value: {},
  })
}

function removeTauriRuntime(): void {
  delete (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
}

describe('presetIpc', () => {
  beforeEach(() => {
    invokeMock.mockReset()
    invokeMock.mockResolvedValue(null)
    installTauriRuntime()
  })

  it('passes load_workbench_preset without an argument object', async () => {
    await presetIpc.load()

    expect(invokeMock).toHaveBeenCalledWith('load_workbench_preset', undefined)
  })

  it('passes save_workbench_preset preset payload', async () => {
    const preset = { name: 'Test preset' } as unknown as WorkbenchPreset

    await presetIpc.save(preset)

    expect(invokeMock).toHaveBeenCalledWith('save_workbench_preset', {
      preset,
    })
  })

  it('passes pick_output_directory without an argument object', async () => {
    await presetIpc.pickOutputDirectory()

    expect(invokeMock).toHaveBeenCalledWith('pick_output_directory', undefined)
  })

  it('keeps load and save as browser-safe no-ops outside Tauri', async () => {
    removeTauriRuntime()
    const preset = { name: 'Browser preset' } as unknown as WorkbenchPreset

    await expect(presetIpc.load()).resolves.toBeNull()
    await expect(presetIpc.save(preset)).resolves.toBeUndefined()
    expect(invokeMock).not.toHaveBeenCalled()
  })
})
