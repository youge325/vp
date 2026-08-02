import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { usePresetStore } from '@/stores/preset'
import { createTestPreset } from '../fixtures/preset'

describe('usePresetStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('replaceDraftPreset deep-clones the input', () => {
    const store = usePresetStore()
    const incoming = createTestPreset()
    incoming.encodeConfig.codec = 'libx264'

    store.replaceDraftPreset(incoming)
    // Mutating the source must not affect the store's clone.
    incoming.encodeConfig.codec = 'hevc_nvenc'

    expect(store.draftPreset.encodeConfig.codec).toBe('libx264')
  })

  it('keeps an existing schema-v2 preset algorithm instead of applying new-product defaults', () => {
    const store = usePresetStore()
    const incoming = createTestPreset()
    incoming.workflowConfig.superResolution.algorithm = 'real-esrgan'
    incoming.workflowConfig.superResolution.tensorBackend = 'onnx'
    incoming.workflowConfig.superResolution.onnxModel = 'legacy-x4.onnx'
    incoming.workflowConfig.superResolution.scaleFactor = 4

    store.replaceDraftPreset(incoming)

    expect(store.draftPreset.workflowConfig.superResolution).toMatchObject({
      algorithm: 'real-esrgan',
      tensorBackend: 'onnx',
      onnxModel: 'legacy-x4.onnx',
      scaleFactor: 4,
    })
  })

  it('patchWorkflow swaps the workflow reference so reactive readers re-run', () => {
    const store = usePresetStore()
    const before = store.draftPreset.workflowConfig

    store.patchWorkflow((wf) => {
      wf.interpolation.enabled = true
      wf.interpolation.multi = 4
    })

    expect(store.draftPreset.workflowConfig).not.toBe(before)
    expect(store.draftPreset.workflowConfig.interpolation.enabled).toBe(true)
    expect(store.draftPreset.workflowConfig.interpolation.multi).toBe(4)
  })

  it('patchEncode mutates encode config without leaking into other slices', () => {
    const store = usePresetStore()
    const workflowBefore = store.draftPreset.workflowConfig

    store.patchEncode((cfg) => {
      cfg.container = 'mkv'
    })

    expect(store.draftPreset.encodeConfig.container).toBe('mkv')
    expect(store.draftPreset.workflowConfig).toBe(workflowBefore)
  })

  it('setPersistenceReady flips the boolean', () => {
    const store = usePresetStore()
    expect(store.presetPersistenceReady).toBe(false)
    store.setPersistenceReady(true)
    expect(store.presetPersistenceReady).toBe(true)
  })
})
