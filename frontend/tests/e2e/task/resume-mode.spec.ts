import { test, expect } from '../fixtures'
import { join } from 'node:path'
import { removeFileWhenUnlocked, waitForNonEmptyFile } from '../utils/files'

function buildTaskRequest(inputPath: string, outputDir: string, resumeMode?: string) {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
    decodeConfig: { mode: 'software' as const, hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: {
      codec: 'h264',
      family: 'cpu',
      container: 'mp4',
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
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    resumeMode: resumeMode ?? 'force-fresh',
  }
}

test.describe('Resume mode', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
  const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')

  test('start_task with resumeMode auto and no existing output succeeds', async ({ tauriPage }) => {
    // Ensure no existing output
    await removeFileWhenUnlocked(outFile)

    const request = buildTaskRequest(inputPath, outputDir, 'auto')

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

  test('check_resume_state with resumeMode auto returns resumed false when no checkpoint exists', async ({ tauriPage }) => {
    await removeFileWhenUnlocked(outFile)

    const request = buildTaskRequest(inputPath, outputDir, 'auto')

    const result = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        return await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
      } catch (error: any) {
        throw new Error(`check_resume_state failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    // format_conversion 路径不返回 resumed 字段（只有 streaming 路径才有）
    expect(result).not.toHaveProperty('resumed')
    expect(result).toHaveProperty('completedChunks')
    expect(result.completedChunks).toBe(0)
    expect(result).toHaveProperty('finalExists')
    expect(result.finalExists).toBe(false)
  })
})
