import { test, expect } from '../fixtures'
import { existsSync, rmSync } from 'fs'

function buildTaskRequest(inputPath: string, outputDir: string) {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
    decodeConfig: { mode: 'software' as const, hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: {
      codec: 'libx265',
      family: 'cpu',
      container: 'mkv',
      keepAudio: true,
      rateControl: { mode: 'crf' as const, value: 23 },
      options: { preset: 'medium' },
    },
    workflowConfig: {
      fpsMode: 'multi' as const,
      processOrder: 'super_resolution_then_interpolation' as const,
      interpolation: {
        enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25',
        scale: 1.0, fp16: false, tensorBackend: 'pytorch' as const, engine: 'cuda',
      },
      superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
      anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    resumeMode: 'force-fresh',
  }
}

test.describe('HEVC output inspection', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
  const outFile = `${outputDir}\\vp-e2e-test_processed.mkv`

  test('hevc+mkv output is inspectable and contains hevc codec info', async ({ tauriPage }) => {
    // Generate HEVC output first
    if (existsSync(outFile)) rmSync(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Wait for output file
    let found = false
    for (let i = 0; i < 120; i++) {
      if (existsSync(outFile)) {
        found = true
        break
      }
      await new Promise((r) => setTimeout(r, 500))
    }
    expect(found).toBe(true)

    // Inspect the HEVC output
    const info = await tauriPage.evaluate(async (path: string) => {
      try {
        // @ts-expect-error
        return await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: path })
      } catch (error: any) {
        throw new Error(`inspect_video failed: ${JSON.stringify({ message: error?.message, code: error?.code, details: error?.details })}`)
      }
    }, outFile)

    expect(info.frames).toBeGreaterThan(0)
    expect(info.fps).toBeGreaterThan(0)
    expect(info.width).toBeGreaterThan(0)
    expect(info.height).toBeGreaterThan(0)
    expect(info.videoCodec).toBeTruthy()
    // HEVC output should have codec info containing hevc or h265
    const codecLower = String(info.videoCodec).toLowerCase()
    expect(codecLower.includes('hevc') || codecLower.includes('h265') || codecLower.includes('h.265')).toBe(true)
    expect(info.duration).toBeGreaterThan(0)
  })
})
