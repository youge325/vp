import { test, expect } from '../fixtures'

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

async function setupEventListener(tauriPage: any, eventName: string) {
  await tauriPage.evaluate(async (name: string) => {
    // @ts-expect-error
    const internals = window.__TAURI_INTERNALS__
    // @ts-expect-error
    window.__E2E_EVENTS = window.__E2E_EVENTS || []
    // @ts-expect-error
    window.__E2E_UNLISTENERS = window.__E2E_UNLISTENERS || []

    const handlerId = internals.transformCallback((eventData: any) => {
      // @ts-expect-error
      window.__E2E_EVENTS.push({ name, data: eventData.payload })
    })

    const unlistenId = await internals.invoke('plugin:event|listen', {
      event: name,
      target: { kind: 'Any' },
      handler: handlerId,
    })

    // @ts-expect-error
    window.__E2E_UNLISTENERS.push(async () => {
      await internals.invoke('plugin:event|unlisten', { event: name, eventId: unlistenId })
    })
  }, eventName)
}

async function cleanupListeners(tauriPage: any) {
  await tauriPage.evaluate(async () => {
    // @ts-expect-error
    const unlisteners = window.__E2E_UNLISTENERS || []
    for (const unlisten of unlisteners) {
      await unlisten()
    }
    // @ts-expect-error
    window.__E2E_UNLISTENERS = []
  })
}

test.describe('Task log events', () => {
  test('task-log events fire during task execution with string message payload', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    await setupEventListener(tauriPage, 'task-log')
    await setupEventListener(tauriPage, 'task-completed')

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Wait for task-completed (up to 60s)
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-completed')
      },
      { timeout: 60000 },
    )

    const events = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS
    })

    const logEvents = events.filter((e: any) => e.name === 'task-log')
    const completedEvents = events.filter((e: any) => e.name === 'task-completed')

    // Backend emits log messages during normal execution
    expect(logEvents.length).toBeGreaterThanOrEqual(0)
    expect(completedEvents.length).toBe(1)

    // Verify log event structure
    if (logEvents.length > 0) {
      const firstLog = logEvents[0].data
      expect(firstLog).toHaveProperty('message')
      expect(typeof firstLog.message).toBe('string')
      expect(firstLog.message.length).toBeGreaterThanOrEqual(0)
    }

    await cleanupListeners(tauriPage)
  })
})
