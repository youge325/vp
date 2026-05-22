import { test, expect } from './fixtures'

function buildTaskRequest(inputPath: string, outputDir: unknown) {
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

test.describe('Config validation', () => {
  // Use check_resume_state (not start_task) because config validation errors
  // are returned synchronously via the invoke result, whereas start_task
  // spawns the backend asynchronously and surfaces errors through events.

  test('check_resume_state with empty output_dir returns structured error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'

    const error = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, buildTaskRequest(inputPath, ''))

    expect(error).not.toBeNull()
    // ShellError::BackendEnvelope serializes as code "backend_envelope";
    // the inner TaskErrorCode (invalid_config) is in the message.
    expect(error.code).toBe('backend_envelope')
    // Pydantic validation messages use the model field name (camelCase).
    expect(error.message).toContain('outputDir')
  })

  test('check_resume_state with whitespace-only output_dir returns structured error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'

    const error = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, buildTaskRequest(inputPath, '   '))

    expect(error).not.toBeNull()
    expect(error.code).toBe('backend_envelope')
    expect(error.message).toContain('outputDir')
  })

  test('check_resume_state with null output_dir returns structured error', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'

    const error = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, buildTaskRequest(inputPath, null))

    expect(error).not.toBeNull()
    // null output_dir may fail at different stages (Pydantic accepts None,
    // but downstream processing will error); verify any structured error.
    expect(error.code).toBeTruthy()
  })
})
