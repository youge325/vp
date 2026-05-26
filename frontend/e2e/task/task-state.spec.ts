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
      // Tauri wraps payload as { event, id, payload }
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

test.describe('Task state machine', () => {
  test('start_task rejects double-start when task is running', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const request = buildTaskRequest(inputPath, outputDir)

    // First call starts the task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task first call failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    // Second call should be rejected synchronously by the state machine
    const error = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, request)

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')

    // Cleanup: cancel the running task
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
      } catch {}
    })
  })

  test('cancel_task on running task emits task-cancelled event', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    await setupEventListener(tauriPage, 'task-progress')
    await setupEventListener(tauriPage, 'task-cancelled')

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Wait for the task to actually start running
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-progress')
      },
      { timeout: 30000 },
    )

    // Cancel the task
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
      } catch (error: any) {
        throw new Error(`cancel_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    // Wait for task-cancelled event
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-cancelled')
      },
      { timeout: 30000 },
    )

    const cancelledEvents = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-cancelled')
    })

    expect(cancelledEvents.length).toBeGreaterThan(0)
    expect(cancelledEvents[0].data).toHaveProperty('reason')
    expect(cancelledEvents[0].data.reason).toBe('user')

    // Verify state was reset — a new task can be started
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task after cancel failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    await cleanupListeners(tauriPage)
  })

  test('duplicate cancel when already cancelling returns error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    // Start a task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // First cancel should succeed (or be ignored if task finished too quickly)
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
      } catch {}
    })

    // Second cancel should be rejected
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    // If the task already finished, cancel returns invalid_input (NoActiveTask).
    // If still cancelling, cancel returns invalid_input (already cancelling).
    // Either way the code should be invalid_input.
    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task pause when cancelling returns error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    // Start and immediately cancel a task
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

    // Pause during cancelling should be rejected
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'pause' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task resume when cancelling returns error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    // Start and immediately cancel a task
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

    // Resume during cancelling should be rejected
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'resume' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })
})
