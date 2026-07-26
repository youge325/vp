import { test, expect } from '../fixtures'
import { join } from 'node:path'
import { removeFileWhenUnlocked, waitForNonEmptyFile } from '../utils/files'

function buildTaskRequest(
  inputPath: string,
  outputDir: string,
  overrides: { encodeConfig?: Record<string, unknown>; outputConfig?: Record<string, unknown> } = {},
) {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000, ...overrides.outputConfig },
    decodeConfig: { mode: 'software' as const, hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: {
      codec: 'h264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf' as const, value: 23 },
      options: { preset: 'medium' },
      ...overrides.encodeConfig,
    },
    workflowConfig: {
      fpsMode: 'multi' as const,
      processOrder: 'super_resolution_then_interpolation' as const,
      interpolation: {
        enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25',
        scale: 1.0, fp16: false, tensorBackend: 'pytorch' as const, engine: 'cuda',
      },
      superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    resumeMode: 'force-fresh',
  }
}

test.describe('Encode options', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

  test('format_conversion with qp rate control produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, {
      encodeConfig: { rateControl: { mode: 'qp', value: 23 } },
    })
    const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')
    await removeFileWhenUnlocked(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForNonEmptyFile(outFile)
    expect(found).toBe(true)
  })

  test('format_conversion with bitrate rate control produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, {
      encodeConfig: { rateControl: { mode: 'bitrate', value: '2000k' } },
    })
    const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')
    await removeFileWhenUnlocked(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForNonEmptyFile(outFile)
    expect(found).toBe(true)
  })

  test('format_conversion with keepAudio false produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, {
      encodeConfig: { keepAudio: false },
    })
    const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')
    await removeFileWhenUnlocked(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForNonEmptyFile(outFile)
    expect(found).toBe(true)
  })

  test('format_conversion with fast preset produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, {
      encodeConfig: { options: { preset: 'fast' } },
    })
    const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')
    await removeFileWhenUnlocked(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForNonEmptyFile(outFile)
    expect(found).toBe(true)
  })
})
