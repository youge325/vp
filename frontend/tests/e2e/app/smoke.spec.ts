import { test, expect } from '../fixtures'
import { join } from 'node:path'
import { waitForNonEmptyFile } from '../utils/files'

test.describe('VP Workbench e2e smoke', () => {
  test('app launches and home module renders', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="app-shell"]')).toBeVisible({ timeout: 15000 })
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })
  })

  test('check_environment returns structured capabilities', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
      return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
    })
    expect(result).toHaveProperty('result')
    expect(result.result).toHaveProperty('ffmpeg')
    expect(result.result).toHaveProperty('runtimeMode')
    expect(result.result.ffmpeg.available).toBe(true)
  })

  test('check_environment result contains all core schema keys', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      // @ts-expect-error
      return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
    })

    expect(result).toHaveProperty('result')
    expect(result.result).toHaveProperty('ffmpeg')
    expect(result.result).toHaveProperty('gpu')
    expect(result.result).toHaveProperty('tensorEngines')
    expect(result.result).toHaveProperty('runtimeMode')
    expect(Array.isArray(result.result.interpolationAlgorithms)).toBe(true)
    expect(Array.isArray(result.result.superResolutionAlgorithms)).toBe(true)
    expect(result.result).not.toHaveProperty('type')
    expect(result.result).not.toHaveProperty('tensorBackends')
    expect(result.result).not.toHaveProperty('rifeModel')
  })

  test('inspect_video parses synthetic test video', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const info = await tauriPage.evaluate(async (path: string) => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: path })
      } catch (error: any) {
        throw new Error(`inspect_video failed: ${JSON.stringify({ message: error?.message, code: error?.code, details: error?.details })}`)
      }
    }, inputPath)

    expect(info.fps).toBeGreaterThan(0)
    expect(info.width).toBeGreaterThan(0)
    expect(info.height).toBeGreaterThan(0)
    expect(info.videoCodec).toBeTruthy()
    expect(Object.keys(info).sort()).toEqual(['fps', 'height', 'videoCodec', 'width'])
  })

  test('start_task with Anime cleanup produces output file', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const outputDir = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'

    const taskRequest = {
      inputPath,
      outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
      decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
      encodeConfig: {
        codec: 'h264',
        family: 'cpu',
        container: 'mp4',
        keepAudio: true,
        rateControl: { mode: 'crf', value: 23 },
        options: { preset: 'medium' },
      },
      workflowConfig: {
        fpsMode: 'multi',
        processOrder: 'super_resolution_then_interpolation',
        interpolation: { enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
        superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
        preprocess: {
          enabled: true,
          filters: [{
            kind: 'anime_cleanup',
            enabled: true,
            params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
          }],
        },
        postprocess: { enabled: false, filters: [] },
      },
      resumeMode: 'force-fresh',
    }

    // 通过 invoke 直接启动任务，然后轮询输出文件
    await tauriPage.evaluate(async (req) => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('start_task', { request: req })
      } catch (error: any) {
        throw new Error(`start_task failed: ${JSON.stringify({ message: error?.message, code: error?.code, details: error?.details })}`)
      }
    }, taskRequest)

    // 等待输出文件出现（最多 60s）
    const outputPath = join(outputDir, 'vp-e2e-test_processed.mp4')
    expect(await waitForNonEmptyFile(outputPath)).toBe(true)
  })
})
