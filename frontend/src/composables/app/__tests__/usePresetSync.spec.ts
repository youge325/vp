import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { InvokeError } from '@/lib/ipc/client'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useIssueStore } from '@/stores/issue'
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

// Phase 6d — ``usePresetSync`` now writes the preset-scoped banner
// state through ``useIssueStore`` (relocated out of ``useMediaStore``).
// These tests verify that the banner surface still reacts to the same
// success / failure paths as before the move.

describe('usePresetSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    loadMock.mockReset()
    saveMock.mockReset()
  })

  it('clears any prior preset operation issue after a successful save', async () => {
    saveMock.mockResolvedValueOnce(undefined)
    const issueStore = useIssueStore()
    issueStore.setIssue('preset', {
      code: TASK_ERROR_CODES.PersistenceFailed,
      message: 'previous failure',
      details: null,
    })

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(issueStore.operationIssue).toBeNull()
  })

  it('saves persisted enhance preferences in the workflow preset payload', async () => {
    saveMock.mockResolvedValueOnce(undefined)
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.processOrder = 'frame_interpolation_then_super_resolution'
      workflow.interpolation.engine = 'tensorrt'
      workflow.superResolution.engine = 'tensorrt'
      workflow.anime.enabled = true
      workflow.anime.profile = 'line-art'
      workflow.anime.denoise = 24
      workflow.anime.edgeBoost = 36
    })

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(saveMock).toHaveBeenCalledOnce()
    expect(saveMock.mock.calls[0]?.[0]).toMatchObject({
      workflowConfig: {
        processOrder: 'frame_interpolation_then_super_resolution',
        interpolation: {
          engine: 'tensorrt',
        },
        superResolution: {
          engine: 'tensorrt',
        },
        anime: {
          enabled: true,
          profile: 'line-art',
          denoise: 24,
          edgeBoost: 36,
        },
      },
    })
  })

  it('routes PersistenceFailed errors to the preset operation issue surface', async () => {
    saveMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.PersistenceFailed, 'disk is full'),
    )
    const issueStore = useIssueStore()

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
    expect(issueStore.operationIssue?.error.message).toContain('disk is full')
  })

  it('treats SchemaMismatch on save as a reset signal, not a banner-only error', async () => {
    saveMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.SchemaMismatch, 'incompatible schema version'),
    )
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    await sync.persistDraft()

    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('resets to defaults and reports SchemaMismatch when load detects an incompatible payload', async () => {
    loadMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.SchemaMismatch, 'workbench preset schema mismatch'),
    )
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    const loaded = await sync.loadPersistedPreset()

    expect(loaded).toBe(false)
    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('reports generic persistence errors during load but still falls back to defaults', async () => {
    loadMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.PersistenceFailed, 'permission denied'),
    )
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    const loaded = await sync.loadPersistedPreset()

    expect(loaded).toBe(false)
    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
  })
})
