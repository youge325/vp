import { test, expect } from './fixtures'

function buildTaskRequest(inputPath: string, outputDir: string) {
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
    },
    resumeMode: 'force-fresh',
  }
}

test.describe('Immediate cancel', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

  test('cancel_task immediately after start_task emits task-cancelled', async ({ tauriPage }) => {
    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_EVENTS = []
      // @ts-expect-error
      window.__E2E_UNLISTENERS = []

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_EVENTS.push({ name: 'task-cancelled', data: eventData.payload })
      })

      const unlistenId = await internals.invoke('plugin:event|listen', {
        event: 'task-cancelled',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      // @ts-expect-error
      window.__E2E_UNLISTENERS.push(async () => {
        await internals.invoke('plugin:event|unlisten', { event: 'task-cancelled', eventId: unlistenId })
      })
    })

    // Start and immediately cancel — no waiting for progress
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
      } catch {}
    })

    // Wait for cancelled event
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-cancelled')
      },
      { timeout: 30000 },
    )

    const events = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS
    })

    expect(events.length).toBeGreaterThan(0)
    expect(events[0].data).toHaveProperty('reason')
    expect(events[0].data.reason).toBe('user')

    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const unlisteners = window.__E2E_UNLISTENERS || []
      for (const unlisten of unlisteners) {
        await unlisten()
      }
    })
  })
})
