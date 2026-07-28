import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TASK_ERROR_CODES } from '@/types/protocol'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'
import { codedError } from './errors'
import { createDeferred } from '../../fixtures/deferred'

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

// ``usePresetSync`` writes the preset-scoped banner
// state through ``useIssueStore`` (relocated out of ``useMediaStore``).
// These tests verify that the banner surface still reacts to the same
// success / failure paths as before the move.

describe('usePresetSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    loadMock.mockReset()
    saveMock.mockReset()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  function startAutoSync() {
    const presetStore = usePresetStore()
    presetStore.setPersistenceReady(true)
    usePresetSync().startAutoSync()
    return presetStore
  }

  async function triggerSave(
    mutator: Parameters<ReturnType<typeof usePresetStore>['patchWorkflow']>[0],
  ) {
    const presetStore = startAutoSync()
    presetStore.patchWorkflow(mutator)
    await nextTick()
    await vi.advanceTimersByTimeAsync(300)
    return presetStore
  }

  it('clears any prior preset operation issue after a successful save', async () => {
    saveMock.mockResolvedValueOnce(undefined)
    const issueStore = useIssueStore()
    issueStore.setIssue('preset', {
      code: TASK_ERROR_CODES.PersistenceFailed,
      message: 'previous failure',
      details: null,
    })

    await triggerSave((workflow) => {
      workflow.interpolation.scale = 0.5
    })

    expect(issueStore.operationIssue).toBeNull()
  })

  it('saves persisted enhance preferences in the workflow preset payload', async () => {
    saveMock.mockResolvedValueOnce(undefined)
    await triggerSave((workflow) => {
      workflow.processOrder = 'frame_interpolation_then_super_resolution'
      workflow.interpolation.engine = 'tensorrt'
      workflow.superResolution.engine = 'tensorrt'
      workflow.preprocess.enabled = true
      workflow.preprocess.filters = [{
        kind: 'anime_cleanup',
        enabled: true,
        params: { profile: 'thin-outline', denoise: 8, edgeBoost: 45 },
      }]
    })

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
        preprocess: {
          enabled: true,
          filters: [{
            kind: 'anime_cleanup',
            enabled: true,
            params: { profile: 'thin-outline', denoise: 8, edgeBoost: 45 },
          }],
        },
      },
    })
  })

  it('routes PersistenceFailed errors to the preset operation issue surface', async () => {
    saveMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.PersistenceFailed, 'disk is full'),
    )
    const issueStore = useIssueStore()

    await triggerSave((workflow) => {
      workflow.interpolation.scale = 0.5
    })

    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
    expect(issueStore.operationIssue?.error.message).toContain('disk is full')
  })

  it('serializes overlapping saves and persists the latest debounced snapshot last', async () => {
    const firstSave = createDeferred()
    saveMock
      .mockImplementationOnce(() => firstSave.promise)
      .mockResolvedValueOnce(undefined)
    const presetStore = startAutoSync()

    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.scale = 0.5
    })
    await nextTick()
    await vi.advanceTimersByTimeAsync(300)

    expect(saveMock).toHaveBeenCalledOnce()
    expect(saveMock.mock.calls[0]?.[0]).toMatchObject({
      workflowConfig: {
        interpolation: { scale: 0.5 },
      },
    })

    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.scale = 0.75
    })
    await nextTick()
    await vi.advanceTimersByTimeAsync(300)

    expect(saveMock).toHaveBeenCalledOnce()

    firstSave.resolve()
    await flushPromises()

    expect(saveMock).toHaveBeenCalledTimes(2)
    expect(saveMock.mock.calls[1]?.[0]).toMatchObject({
      workflowConfig: {
        interpolation: { scale: 0.75 },
      },
    })
  })

  it('lets only the latest save generation update the preset issue surface', async () => {
    const firstSave = createDeferred()
    const latestSave = createDeferred()
    saveMock
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => latestSave.promise)
    const issueStore = useIssueStore()
    const presetStore = startAutoSync()

    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.scale = 0.5
    })
    await nextTick()
    await vi.advanceTimersByTimeAsync(300)

    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.scale = 0.75
    })
    await nextTick()
    await vi.advanceTimersByTimeAsync(300)

    firstSave.reject(codedError(TASK_ERROR_CODES.PersistenceFailed, 'stale failure'))
    await flushPromises()

    expect(saveMock).toHaveBeenCalledTimes(2)
    expect(issueStore.operationIssue).toBeNull()

    latestSave.reject(codedError(TASK_ERROR_CODES.PersistenceFailed, 'latest failure'))
    await flushPromises()

    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.message).toContain('latest failure')
  })

  it('treats SchemaMismatch on save as a reset signal, not a banner-only error', async () => {
    saveMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.SchemaMismatch, 'incompatible schema version'),
    )
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    await triggerSave((workflow) => {
      workflow.interpolation.scale = 0.5
    })

    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('resets, rebuilds and reports SchemaMismatch when load isolates an incompatible payload', async () => {
    loadMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.SchemaMismatch, 'workbench preset schema mismatch'),
    )
    saveMock.mockResolvedValueOnce(undefined)
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    await sync.loadPersistedPreset()

    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(saveMock).toHaveBeenCalledOnce()
    expect(saveMock).toHaveBeenCalledWith(presetStore.draftPreset)
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.SchemaMismatch)
  })

  it('keeps the preset issue actionable when rebuilding isolated data fails', async () => {
    loadMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.SchemaMismatch, 'workbench preset schema mismatch'),
    )
    saveMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.PersistenceFailed, 'replacement write denied'),
    )
    const issueStore = useIssueStore()

    await usePresetSync().loadPersistedPreset()

    expect(saveMock).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.scope).toBe('preset')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
    expect(issueStore.operationIssue?.error.message).toContain('replacement write denied')
  })

  it('reports generic persistence errors during load but still falls back to defaults', async () => {
    loadMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.PersistenceFailed, 'permission denied'),
    )
    const issueStore = useIssueStore()
    const presetStore = usePresetStore()
    const replaceSpy = vi.spyOn(presetStore, 'replaceDraftPreset')

    const sync = usePresetSync()
    await sync.loadPersistedPreset()

    expect(replaceSpy).toHaveBeenCalledOnce()
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.PersistenceFailed)
  })
})
