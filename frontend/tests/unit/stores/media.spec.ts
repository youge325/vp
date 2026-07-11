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
    superResolution: {
      enabled: false,
      scaleFactor: 2,
      algorithm: 'placeholder',
      onnxModel: '',
      tensorBackend: 'onnx',
      engine: 'cuda',
      numFrames: 10,
    },
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

  // Phase 6d — banner-state assertions moved to ``stores/__tests__/issue.spec.ts``.
  // Lock in that ``useMediaStore`` no longer leaks the relocated surface so a
  // future regression that re-introduces it fails loudly here.
  it('does not expose the relocated operationIssue surface', () => {
    const store = useMediaStore()
    expect('operationIssue' in store).toBe(false)
    expect('setOperationIssue' in store).toBe(false)
    expect('clearOperationIssue' in store).toBe(false)
  })

  // Phase 13.1 — ``taskState`` / ``issue`` / ``lastOutputPath`` 拆到独立
  // 的 ``useMediaRunState`` store。锁定 useMediaStore 不再暴露这些 mutator。
  it('does not expose the relocated run-state mutators after Phase 13.1', () => {
    const store = useMediaStore()
    expect('setItemTaskState' in store).toBe(false)
    expect('setItemIssue' in store).toBe(false)
    expect('setItemLastOutputPath' in store).toBe(false)
    expect('resetItemRunState' in store).toBe(false)
    expect('resetItemsRunState' in store).toBe(false)
  })

  // Phase 17 — ``forEachEditableItem`` 下线(grep 0 production callers,
  // 只有 getEditableTargetIds 真在用)。
  it('does not expose forEachEditableItem after Phase 17', () => {
    const store = useMediaStore()
    expect('forEachEditableItem' in store).toBe(false)
  })
})
