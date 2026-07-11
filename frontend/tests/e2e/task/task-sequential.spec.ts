import { test, expect } from '../fixtures'
import { existsSync, statSync, rmSync } from 'fs'
import { join } from 'node:path'

function buildTaskRequest(inputPath: string, outputDir: string, overrides: { encodeConfig?: Record<string, unknown> } = {}) {
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

test.describe('Sequential task execution', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
  const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
  const outFile = join(outputDir, 'vp-e2e-test_processed.mp4')

  test('two consecutive start_task calls both succeed after state reset', async ({ tauriPage }) => {
    // Clean up any existing output
    await removeIfExists(outFile)

    await setupEventListener(tauriPage, 'task-completed')

    // First task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task first call failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Wait for first completion
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-completed')
      },
      { timeout: 60000 },
    )

    const firstEvents = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-completed')
    })
    expect(firstEvents.length).toBe(1)
    expect(firstEvents[0].data).toHaveProperty('outputPath')
    expect(firstEvents[0].data.processedFrames).toBeGreaterThan(0)

    // Clean output for second task
    await removeIfExists(outFile)

    // Second task with different encode options
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task second call failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir, { encodeConfig: { options: { preset: 'fast' } } }))

    // Wait for second completion — need to wait for a NEW completed event
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-completed').length >= 2
      },
      { timeout: 60000 },
    )

    const allEvents = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-completed')
    })
    expect(allEvents.length).toBe(2)
    expect(allEvents[1].data).toHaveProperty('outputPath')
    expect(allEvents[1].data.processedFrames).toBeGreaterThan(0)

    await cleanupListeners(tauriPage)
  })

  test('start_task after cancel_task can start a new task', async ({ tauriPage }) => {
    await removeIfExists(outFile)

    await setupEventListener(tauriPage, 'task-cancelled')
    await setupEventListener(tauriPage, 'task-completed')

    // Start first task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Cancel it
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
      } catch {}
    })

    // Wait for cancelled
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_EVENTS.some((e: any) => e.name === 'task-cancelled')
      },
      { timeout: 30000 },
    )

    // Clean and start new task
    await removeIfExists(outFile)
    const completedBeforeRestart = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-completed').length
    })

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task after cancel failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir, { encodeConfig: { options: { preset: 'fast' } } }))

    // Wait for completed (not cancelled)
    await tauriPage.waitForFunction(
      (beforeCount) => {
        // @ts-expect-error
        return window.__E2E_EVENTS.filter((e: any) => e.name === 'task-completed').length > beforeCount
      },
      completedBeforeRestart,
      { timeout: 60000 },
    )

    const events = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_EVENTS
    })

    const cancelledEvents = events.filter((e: any) => e.name === 'task-cancelled')
    const completedEvents = events.filter((e: any) => e.name === 'task-completed')

    expect(cancelledEvents.length).toBeGreaterThan(0)
    expect(completedEvents.length).toBeGreaterThan(completedBeforeRestart)

    await cleanupListeners(tauriPage)
  })
})
