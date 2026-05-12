import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { InvokeError } from '@/lib/ipc/client'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'

// Mock the preset IPC endpoints so we can control success/failure per test.
const loadMock = vi.fn()
const saveMock = vi.fn()

vi.mock('@/lib/ipc/endpoints/preset', () => ({
  presetIpc: {
    load: () => loadMock(),
    save: (preset: unknown) => saveMock(preset),
    pickOutputDirectory: vi.fn(),
  },
}))

import { usePresetSync } from '@/composables/app/usePresetSync'

describe('usePresetSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    loadMock.mockReset()
    saveMock.mockReset()
  })

  it('clears any prior preset operation issue after a successful save', async () => {
    saveMock.mockResolvedValueOnce(undefined)
    const mediaStore = useMediaStore()
    mediaStore.setOperationIssue('preset', {
      code: TASK_ERROR_CODES.PersistenceFailed,
      message: 'previous failure',
    })

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(mediaStore.operationIssue).toBeNull()
  })

  it('routes PersistenceFailed errors to the preset operation issue surface', async () => {
    saveMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.PersistenceFailed, 'disk is full'),
    )
    const mediaStore = useMediaStore()

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(mediaStore.operationIssue?.scope).toBe('preset')
    expect(mediaStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
    expect(mediaStore.operationIssue?.error.message).toContain('disk is full')
  })

  it('treats SchemaMismatch on save as a reset signal, not a banner-only error', async () => {
    saveMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.SchemaMismatch, 'incompatible schema version'),
    )
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(mediaStore.operationIssue?.scope).toBe('preset')
    expect(mediaStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('resets to defaults and reports SchemaMismatch when load detects an incompatible payload', async () => {
    loadMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.SchemaMismatch, 'workbench preset schema mismatch'),
    )
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    const loaded = await sync.loadPersistedPreset()

    expect(loaded).toBe(false)
    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(mediaStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('reports generic persistence errors during load but still falls back to defaults', async () => {
    loadMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.PersistenceFailed, 'permission denied'),
    )
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    const loaded = await sync.loadPersistedPreset()

    expect(loaded).toBe(false)
    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(mediaStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
  })
})
