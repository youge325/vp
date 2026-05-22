import { test, expect } from './fixtures'
import { existsSync } from 'fs'

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
        enabled: false,
        targetFps: 60,
        multi: 2,
        algorithm: 'rife',
        model: '4.25',
        scale: 1.0,
        fp16: false,
        tensorBackend: 'pytorch' as const,
        engine: 'cuda',
      },
      superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
      anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    resumeMode: 'force-fresh',
  }
}

test.describe('Task resume state', () => {
  test('check_resume_state for fresh video returns format_conversion metadata', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const request = buildTaskRequest(inputPath, outputDir)

    const result = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
      } catch (error: any) {
        throw new Error(`check_resume_state failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    expect(result).toHaveProperty('pipeline_kind')
    expect(result.pipeline_kind).toBe('format_conversion')
    expect(result).toHaveProperty('finalExists')
    expect(typeof result.finalExists).toBe('boolean')
    expect(result).toHaveProperty('sidecarExists')
    expect(result.sidecarExists).toBe(false)
    expect(result).toHaveProperty('completedChunks')
    expect(result.completedChunks).toBe(0)
    expect(result).toHaveProperty('completedOutputFrames')
    expect(result.completedOutputFrames).toBe(0)
    expect(result).toHaveProperty('nextSourceFrame')
    expect(result.nextSourceFrame).toBe(0)
    expect(result).toHaveProperty('totalOutputFrames')
    expect(result.totalOutputFrames).toBeGreaterThan(0)
    expect(result).toHaveProperty('outputPath')
    expect(result.outputPath).toBeTruthy()
    expect(result).toHaveProperty('input_path')
    expect(result.input_path).toBe(inputPath)
  })

  test('check_resume_state when output exists returns finalExists: true', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const request = buildTaskRequest(inputPath, outputDir)
    const outputPath = `${outputDir}\\vp-e2e-test_processed.mp4`

    // Ensure output file exists by running a task and waiting for completion
    // via the task-completed event to avoid race with force-fresh deletion.
    await tauriPage.evaluate(async (req) => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_RESUME_EVENT = null

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_RESUME_EVENT = eventData.payload
      })

      // @ts-expect-error
      window.__E2E_RESUME_UNLISTEN = await internals.invoke('plugin:event|listen', {
        event: 'task-completed',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      try {
        // @ts-expect-error
        await internals.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    // Wait for task-completed event (up to 60s)
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_RESUME_EVENT !== null
      },
      { timeout: 60000 },
    )

    // Verify file was produced
    expect(existsSync(outputPath)).toBe(true)

    // Cleanup listener
    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      await internals.invoke('plugin:event|unlisten', { event: 'task-completed', eventId: window.__E2E_RESUME_UNLISTEN })
    })

    // Now check resume state — should see finalExists: true
    const result = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        return await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
      } catch (error: any) {
        throw new Error(`check_resume_state failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, request)

    expect(result).toHaveProperty('pipeline_kind')
    expect(result.pipeline_kind).toBe('format_conversion')
    expect(result).toHaveProperty('finalExists')
    expect(result.finalExists).toBe(true)
    expect(result).toHaveProperty('sidecarExists')
    expect(result.sidecarExists).toBe(false)
    expect(result).toHaveProperty('completedChunks')
    expect(result.completedChunks).toBe(0)
  })

  test('start_task with resumeMode auto and existing output emits task-error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
    const outputPath = `${outputDir}\\vp-e2e-test_processed.mp4`

    // Step 1: Produce output file with force-fresh
    await tauriPage.evaluate(async (req) => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_RESUME_EVENT = null

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_RESUME_EVENT = eventData.payload
      })

      // @ts-expect-error
      window.__E2E_RESUME_UNLISTEN = await internals.invoke('plugin:event|listen', {
        event: 'task-completed',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      try {
        // @ts-expect-error
        await internals.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, buildTaskRequest(inputPath, outputDir))

    // Wait for first task to complete
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_RESUME_EVENT !== null
      },
      { timeout: 60000 },
    )

    expect(existsSync(outputPath)).toBe(true)

    // Cleanup first listener
    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      await internals.invoke('plugin:event|unlisten', { event: 'task-completed', eventId: window.__E2E_RESUME_UNLISTEN })
    })

    // Step 2: Listen for task-error and start with auto mode
    const autoRequest = { ...buildTaskRequest(inputPath, outputDir), resumeMode: 'auto' }

    await tauriPage.evaluate(async (req) => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      window.__E2E_ERROR_EVENT = null

      const handlerId = internals.transformCallback((eventData: any) => {
        // @ts-expect-error
        window.__E2E_ERROR_EVENT = eventData.payload
      })

      // @ts-expect-error
      window.__E2E_ERROR_UNLISTEN = await internals.invoke('plugin:event|listen', {
        event: 'task-error',
        target: { kind: 'Any' },
        handler: handlerId,
      })

      try {
        // @ts-expect-error
        await internals.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task auto failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, autoRequest)

    // Wait for task-error event
    await tauriPage.waitForFunction(
      () => {
        // @ts-expect-error
        return window.__E2E_ERROR_EVENT !== null
      },
      { timeout: 30000 },
    )

    const errorEvent = await tauriPage.evaluate(() => {
      // @ts-expect-error
      return window.__E2E_ERROR_EVENT
    })

    expect(errorEvent).toHaveProperty('code')
    expect(errorEvent.code).toBe('resume_conflict')

    // Cleanup
    await tauriPage.evaluate(async () => {
      // @ts-expect-error
      const internals = window.__TAURI_INTERNALS__
      // @ts-expect-error
      await internals.invoke('plugin:event|unlisten', { event: 'task-error', eventId: window.__E2E_ERROR_UNLISTEN })
    })
  })
})
