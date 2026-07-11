import { test, expect } from '../fixtures'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

test.describe('Error handling', () => {
  test('inspect_video on missing file returns structured error', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: 'C:/nonexistent/vp-e2e-missing.mp4' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBeTruthy()
    expect(error.message).toBeTruthy()
  })

  test('cancel_task when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task pause when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'pause' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task resume when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'resume' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('inspect_video on non-video file returns structured error', async ({ tauriPage }) => {
    const { writeFileSync, unlinkSync } = await import('fs')
    const notAVideo = join(tmpdir(), 'vp-e2e-not-a-video.txt')
    writeFileSync(notAVideo, 'this is not a video file')

    const error = await tauriPage.evaluate(async (path: string) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: path })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, notAVideo)

    unlinkSync(notAVideo)

    expect(error).not.toBeNull()
    expect(error.code).toBeTruthy()
    expect(error.message).toBeTruthy()
  })

  test('check_resume_state on missing input returns structured error', async ({ tauriPage }) => {
    const request = {
      inputPath: 'C:/nonexistent/vp-e2e-missing.mp4',
      outputConfig: { outputDir: 'C:/tmp', openOnComplete: false, segmentFrames: 1000 },
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
        resumeMode: 'force-fresh',
      },
    }

    const error = await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('check_resume_state', { request: req })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    }, request)

    expect(error).not.toBeNull()
    expect(error.code).toBeTruthy()
    expect(error.message).toBeTruthy()
  })
})
