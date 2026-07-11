import { test, expect } from '../fixtures'
import { createTaskOutputDir, taskInputPath } from './helpers'

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

async function taskEventCount(tauriPage: any, eventName: string) {
  return await tauriPage.evaluate((name: string) => {
    // @ts-expect-error
    return (window.__E2E_EVENTS || []).filter((e: any) => e.name === name).length
  }, eventName) as number
}

async function invokeCancelTask(tauriPage: any) {
  return await tauriPage.evaluate(async () => {
    try {
      // @ts-expect-error
      await window.__TAURI_INTERNALS__.invoke('cancel_task')
      return true
    } catch {
      return false
    }
  }) as boolean
}

async function waitForTaskCancelledAfter(tauriPage: any, previousCount: number) {
  await tauriPage.waitForFunction(
    (count: number) => {
      // @ts-expect-error
      return (window.__E2E_EVENTS || []).filter((e: any) => e.name === 'task-cancelled').length > count
    },
    previousCount,
    { timeout: 30000 },
  )
}

async function cancelTaskAndWait(tauriPage: any) {
  await setupEventListener(tauriPage, 'task-cancelled')
  const previousCount = await taskEventCount(tauriPage, 'task-cancelled')
  const cancelStarted = await invokeCancelTask(tauriPage)
  if (cancelStarted) {
    await waitForTaskCancelledAfter(tauriPage, previousCount)
  }
  await cleanupListeners(tauriPage)
}

test.describe('Task state machine', () => {
  test('start_task rejects double-start when task is running', async ({ tauriPage }) => {
    const inputPath = taskInputPath()
    const outputDir = createTaskOutputDir('task-state-double-start')
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

    await cancelTaskAndWait(tauriPage)
  })

  test('cancel_task on running task emits task-cancelled event', async ({ tauriPage }) => {
    const inputPath = taskInputPath()
    const outputDir = createTaskOutputDir('task-state-cancel-running')

    await setupEventListener(tauriPage, 'task-cancelled')

    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

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

    await cancelTaskAndWait(tauriPage)
  })

  test('duplicate cancel when already cancelling returns error', async ({ tauriPage }) => {
    const inputPath = taskInputPath()
    const outputDir = createTaskOutputDir('task-state-duplicate-cancel')

    // Start a task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    await setupEventListener(tauriPage, 'task-cancelled')
    const previousCount = await taskEventCount(tauriPage, 'task-cancelled')
    const firstCancelStarted = await invokeCancelTask(tauriPage)

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
    if (firstCancelStarted) {
      await waitForTaskCancelledAfter(tauriPage, previousCount)
    }
    await cleanupListeners(tauriPage)
  })

  test('control_task pause when cancelling returns error', async ({ tauriPage }) => {
    const inputPath = taskInputPath()
    const outputDir = createTaskOutputDir('task-state-pause-cancelling')

    // Start and immediately cancel a task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    await setupEventListener(tauriPage, 'task-cancelled')
    const previousCount = await taskEventCount(tauriPage, 'task-cancelled')
    const firstCancelStarted = await invokeCancelTask(tauriPage)

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
    if (firstCancelStarted) {
      await waitForTaskCancelledAfter(tauriPage, previousCount)
    }
    await cleanupListeners(tauriPage)
  })

  test('control_task resume when cancelling returns error', async ({ tauriPage }) => {
    const inputPath = taskInputPath()
    const outputDir = createTaskOutputDir('task-state-resume-cancelling')

    // Start and immediately cancel a task
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    await setupEventListener(tauriPage, 'task-cancelled')
    const previousCount = await taskEventCount(tauriPage, 'task-cancelled')
    const firstCancelStarted = await invokeCancelTask(tauriPage)

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
    if (firstCancelStarted) {
      await waitForTaskCancelledAfter(tauriPage, previousCount)
    }
    await cleanupListeners(tauriPage)
  })
})
