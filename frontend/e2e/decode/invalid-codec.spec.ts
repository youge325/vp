import { test, expect } from '../fixtures'
import { existsSync, rmSync } from 'fs'

function buildTaskRequest(
  inputPath: string,
  outputDir: string,
  codec: string,
) {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
    decodeConfig: { mode: 'software' as const, hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: {
      codec,
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
    },
    resumeMode: 'force-fresh',
  }
}

test.describe('Invalid codec rejection', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
  const outFile = `${outputDir}\\vp-e2e-test_processed.mp4`

  test('start_task with nonexistent codec returns structured task-error event', async ({ tauriPage }) => {
    if (existsSync(outFile)) rmSync(outFile)

    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_EVENTS = []
      // @ts-expect-error
      window.__E2E_UNLISTENERS = []

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_EVENTS.push({ name: 'task-error', data: eventData.payload })
      })

      const unlistenId = await internals.invoke('plugin:event|listen', {
        event: 'task-error',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      // @ts-expect-error
      window.__E2E_UNLISTENERS.push(async () => {
        await internals.invoke('plugin:event|unlisten', { event: 'task-error', eventId: unlistenId })
      })
    })

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir, 'nonexistent_codec_xyz'))

    // Wait for task-error event (should arrive quickly — config validation fails early)
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-error')
      },
      { timeout: 15000 },
    )

    const events = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS
    })

    const errorEvents = events.filter((e: any) => e.name === 'task-error')
    expect(errorEvents.length).toBeGreaterThanOrEqual(1)

    const error = errorEvents[0].data
    expect(error).toHaveProperty('code')
    expect(error).toHaveProperty('message')
    expect(error.message.length).toBeGreaterThan(0)

    // Cleanup listeners
    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const unlisteners = window.__E2E_UNLISTENERS || []
      for (const unlisten of unlisteners) {
        await unlisten()
      }
    })
  })

  test('start_task with invalid container returns structured task-error event', async ({ tauriPage }) => {
    const request = buildTaskRequest(inputPath, outputDir, 'h264')
    ;(request as any).encodeConfig.container = 'invalid_container_xyz'

    if (existsSync(outFile)) rmSync(outFile)

    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_EVENTS = []
      // @ts-expect-error
      window.__E2E_UNLISTENERS = []

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_EVENTS.push({ name: 'task-error', data: eventData.payload })
      })

      const unlistenId = await internals.invoke('plugin:event|listen', {
        event: 'task-error',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      // @ts-expect-error
      window.__E2E_UNLISTENERS.push(async () => {
        await internals.invoke('plugin:event|unlisten', { event: 'task-error', eventId: unlistenId })
      })
    })

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-error')
      },
      { timeout: 15000 },
    )

    const events = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS
    })

    const errorEvents = events.filter((e: any) => e.name === 'task-error')
    expect(errorEvents.length).toBeGreaterThanOrEqual(1)

    const error = errorEvents[0].data
    expect(error).toHaveProperty('code')
    expect(error).toHaveProperty('message')

    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const unlisteners = window.__E2E_UNLISTENERS || []
      for (const unlisten of unlisteners) {
        await unlisten()
      }
    })
  })
})
