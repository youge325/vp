import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { usePresetStore } from '@/stores/preset'
import type { WorkbenchPreset } from '@/types/protocol'

function defaultPreset(): WorkbenchPreset {
  return {
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
        autoDownloadWeights: false,
      },
      anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
    outputConfig: { outputDir: '', openOnComplete: true, segmentFrames: 1000 },
  }
}

describe('usePresetStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('replaceDraftPreset deep-clones the input', () => {
    const store = usePresetStore()
    const incoming = defaultPreset()
    incoming.encodeConfig.codec = 'libx264'

    store.replaceDraftPreset(incoming)
    // Mutating the source must not affect the store's clone.
    incoming.encodeConfig.codec = 'hevc_nvenc'

    expect(store.draftPreset.encodeConfig.codec).toBe('libx264')
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

  // Phase 17 — ``setDecode / setEncode / setWorkflow / setOutput`` 4 个
  // 直接替换型 setter 全是 dead exports(grep 0 production callers),
  // callsite 全部走 ``patchX(mutator)`` 路径。
  it('does not expose direct setters after Phase 17', () => {
    const store = usePresetStore()
    expect('setDecode' in store).toBe(false)
    expect('setEncode' in store).toBe(false)
    expect('setWorkflow' in store).toBe(false)
    expect('setOutput' in store).toBe(false)
  })
})
