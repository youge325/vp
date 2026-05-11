import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useMediaStore } from '@/stores/media'
import { createMediaItem } from '@/services/media/factory'
import type { WorkbenchPreset } from '@/types/protocol'

const samplePreset: WorkbenchPreset = {
  decodeConfig: { mode: 'software', hwaccel: '', hwaccelDevice: '', decoder: 'software', options: {} },
  workflowConfig: {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: { enabled: false, targetFps: 60, multi: 2, model: '4.25', onnxModel: '', scale: 1, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
    superResolution: { enabled: false, scaleFactor: 2, algorithm: 'placeholder', onnxModel: '' },
    anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
    preprocess: { enabled: false, filters: [] },
    postprocess: { enabled: false, filters: [] },
  },
  encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
  outputConfig: { outputDir: '', openOnComplete: true, segmentFrames: 1000 },
}

describe('useMediaStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('appendItems promotes the first appended item as active', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', samplePreset)
    const b = createMediaItem('/b.mp4', samplePreset)

    store.appendItems([a, b])

    expect(store.mediaItems).toHaveLength(2)
    expect(store.activeItemId).toBe(a.id)
  })

  it('appendItems with empty array is a no-op', () => {
    const store = useMediaStore()
    store.appendItems([])
    expect(store.mediaItems).toHaveLength(0)
    expect(store.activeItemId).toBeNull()
  })

  it('removeItem moves activeItemId forward when removing the active item', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', samplePreset)
    const b = createMediaItem('/b.mp4', samplePreset)
    store.appendItems([a, b])

    store.removeItem(a.id)

    expect(store.mediaItems).toHaveLength(1)
    expect(store.activeItemId).toBe(b.id)
  })

  it('selectAll toggles every item', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', samplePreset)
    const b = createMediaItem('/b.mp4', samplePreset)
    store.appendItems([a, b])

    store.selectAll(false)
    expect(store.mediaItems.every((item) => !item.selected)).toBe(true)

    store.selectAll(true)
    expect(store.allSelected).toBe(true)
  })

  it('setOperationIssue and clearOperationIssue track a scope-tagged error', () => {
    const store = useMediaStore()
    expect(store.operationIssue).toBeNull()

    store.setOperationIssue('input', { code: 'pick_inputs_failed', message: 'no files' })
    expect(store.operationIssue?.scope).toBe('input')
    expect(store.operationIssue?.error.code).toBe('pick_inputs_failed')

    store.clearOperationIssue('encode') // different scope — should NOT clear
    expect(store.operationIssue?.scope).toBe('input')

    store.clearOperationIssue('input')
    expect(store.operationIssue).toBeNull()
  })

  it('resetItemRunState restores idle defaults while preserving logs when asked', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', samplePreset)
    store.appendItems([a])

    store.setItemTaskState(a.id, {
      ...a.taskState,
      status: 'completed',
      percent: 100,
      logs: ['line-1', 'line-2'],
    })
    store.setItemLastOutputPath(a.id, 'D:/out.mp4')

    store.resetItemRunState(a.id, true)
    const refreshed = store.findItem(a.id)!
    expect(refreshed.taskState.status).toBe('idle')
    expect(refreshed.taskState.percent).toBe(0)
    expect(refreshed.taskState.logs).toEqual(['line-1', 'line-2'])
    expect(refreshed.lastOutputPath).toBe('')
  })
})
