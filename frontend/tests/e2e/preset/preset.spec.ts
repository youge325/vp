import { test, expect } from '../fixtures'
import type { WorkbenchPreset } from '@/types/protocol'
import { invokeTauri } from '../utils/task-runtime'

function buildPreset(outputDir: string): WorkbenchPreset {
  return {
    decodeConfig: {
      mode: 'software',
      hwaccel: null,
      hwaccelDevice: null,
      decoder: 'software',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'multi',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: {
        enabled: false,
        targetFps: 60,
        multi: 2,
        algorithm: 'rife',
        model: '4.25',
        onnxModel: null,
        scale: 1.0,
        fp16: false,
        tensorBackend: 'pytorch',
        engine: 'cuda',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2.0,
        algorithm: 'realesrgan',
        onnxModel: null,
        tensorBackend: 'pytorch',
        engine: 'cuda',
        numFrames: 10,
      },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    encodeConfig: {
      codec: 'libx264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf', value: 18 },
      options: {},
    },
    outputConfig: {
      outputDir,
      openOnComplete: true,
      segmentFrames: 1000,
    },
  }
}

test.describe('Preset persistence', () => {
  test('round-trips and atomically overwrites the persisted preset', async ({ tauriPage }) => {
    const dir1 = 'D:/vp-e2e-preset-test-v1'
    const dir2 = 'D:/vp-e2e-preset-test-v2'

    await invokeTauri(tauriPage, 'save_workbench_preset', { preset: buildPreset(dir1) })
    const first = await invokeTauri<any>(tauriPage, 'load_workbench_preset')
    expect(first.outputConfig.outputDir).toBe(dir1)
    expect(first.encodeConfig.rateControl.value).toBe(18)

    await invokeTauri(tauriPage, 'save_workbench_preset', { preset: buildPreset(dir2) })
    const overwritten = await invokeTauri<any>(tauriPage, 'load_workbench_preset')
    expect(overwritten.outputConfig.outputDir).toBe(dir2)
    expect(overwritten.workflowConfig.interpolation.algorithm).toBe('rife')
  })
})
