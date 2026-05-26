import { test, expect } from '../fixtures'
import { existsSync, statSync } from 'fs'

function buildTaskRequest(
  inputPath: string,
  outputDir: string,
  codec: string,
  container: string,
  rateControl?: { mode: string; value: number },
) {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
    decodeConfig: { mode: 'software' as const, hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: {
      codec,
      family: 'cpu',
      container,
      keepAudio: true,
      rateControl: rateControl ?? { mode: 'crf', value: 23 },
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

test.describe('Codec and container variants', () => {
  test('format_conversion with hevc + mkv produces output file', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const request = buildTaskRequest(inputPath, outputDir, 'libx265', 'mkv')

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const outputPath = `${outputDir}\\vp-e2e-test_processed.mkv`
    let found = false
    for (let i = 0; i < 120; i++) {
      if (existsSync(outputPath) && statSync(outputPath).size > 0) {
        found = true
        break
      }
      await new Promise((r) => setTimeout(r, 500))
    }

    expect(found).toBe(true)
  })

  test('format_conversion with cq rate control produces output file', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const request = buildTaskRequest(inputPath, outputDir, 'h264', 'mp4', { mode: 'cq', value: 23 })

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const outputPath = `${outputDir}\\vp-e2e-test_processed.mp4`
    let found = false
    for (let i = 0; i < 120; i++) {
      if (existsSync(outputPath) && statSync(outputPath).size > 0) {
        found = true
        break
      }
      await new Promise((r) => setTimeout(r, 500))
    }

    expect(found).toBe(true)
  })
})
