import { test, expect } from './fixtures'

function buildPreset(outputDir: string) {
  return {
    decodeConfig: {
      mode: 'software' as const,
      decoder: 'software',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'multi' as const,
      processOrder: 'super_resolution_then_interpolation' as const,
      interpolation: {
        enabled: false,
        targetFps: 60,
        multi: 2,
        algorithm: 'rife',
        model: '4.25',
        scale: 1.0,
        fp16: false,
        tensorBackend: 'pytorch' as const,
        engine: 'cuda',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2.0,
        algorithm: 'realesrgan',
      },
      anime: {
        enabled: false,
        profile: 'clean-lines',
        denoise: 10,
        edgeBoost: 15,
      },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    encodeConfig: {
      codec: 'libx264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf' as const, value: 18 },
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
  test('save and load preset round-trips', async ({ tauriPage }) => {
    const outputDir = 'D:/vp-e2e-preset-test'
    const preset = buildPreset(outputDir)

    await tauriPage.evaluate(async (p) => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('save_workbench_preset', { preset: p })
      } catch (error: any) {
        throw new Error(`save_workbench_preset failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, preset)

    const loaded = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('load_workbench_preset')
      } catch (error: any) {
        throw new Error(`load_workbench_preset failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    expect(loaded).not.toBeNull()
    expect(loaded.decodeConfig.mode).toBe('software')
    expect(loaded.workflowConfig.fpsMode).toBe('multi')
    expect(loaded.workflowConfig.interpolation.algorithm).toBe('rife')
    expect(loaded.encodeConfig.codec).toBe('libx264')
    expect(loaded.encodeConfig.rateControl.mode).toBe('crf')
    expect(loaded.outputConfig.segmentFrames).toBe(1000)
    expect(loaded.outputConfig.outputDir).toBe(outputDir)
  })
})
