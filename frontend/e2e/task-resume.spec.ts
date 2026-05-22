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
})
