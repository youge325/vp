import { test, expect } from '../fixtures'
import { existsSync, statSync, rmSync } from 'fs'

function buildTaskRequest(
  inputPath: string,
  outputDir: string,
  workflowOverrides: Record<string, unknown> = {},
) {
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
      anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
      ...workflowOverrides,
    },
    resumeMode: 'force-fresh',
  }
}

async function waitForOutputFile(outputPath: string, maxWaitMs: number = 60000): Promise<boolean> {
  const interval = 500
  const iterations = maxWaitMs / interval
  for (let i = 0; i < iterations; i++) {
    if (existsSync(outputPath) && statSync(outputPath).size > 0) {
      return true
    }
    await new Promise((r) => setTimeout(r, interval))
  }
  return false
}

async function removeIfExists(outputPath: string, maxWaitMs: number = 15000): Promise<void> {
  const interval = 250
  const deadline = Date.now() + maxWaitMs
  let lastError: unknown

  while (Date.now() <= deadline) {
    if (!existsSync(outputPath)) {
      return
    }
    try {
      rmSync(outputPath)
      return
    } catch (error) {
      lastError = error
      await new Promise((resolve) => setTimeout(resolve, interval))
    }
  }

  throw lastError
}

test.describe('Workflow config variants', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

  test('format_conversion with fpsMode target produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, { fpsMode: 'target' })
    const outFile = `${outputDir}\\vp-e2e-test_processed.mp4`
    await removeIfExists(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForOutputFile(outFile)
    expect(found).toBe(true)
  })

  test('format_conversion with processOrder frame_interpolation_then_super_resolution produces output file', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, {
      processOrder: 'frame_interpolation_then_super_resolution',
    })
    const outFile = `${outputDir}\\vp-e2e-test_processed.mp4`
    await removeIfExists(outFile)

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    const found = await waitForOutputFile(outFile)
    expect(found).toBe(true)
  })
})
