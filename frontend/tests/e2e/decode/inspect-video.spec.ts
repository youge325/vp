import { test, expect } from '../fixtures'

test.describe('Video inspection', () => {
  const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'

  test('inspect_video returns the minimal media metadata contract', async ({ tauriPage }) => {
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

    // Type assertions for known synthetic video shape
    expect(info.width).toBe(320)
    expect(info.height).toBe(180)
    expect(info.fps).toBe(10)

    expect(info.videoCodec).toBeTruthy()
    expect(typeof info.videoCodec).toBe('string')
    expect(Object.keys(info).sort()).toEqual(['fps', 'height', 'videoCodec', 'width'])
  })

  test('inspect_video on nonexistent file returns structured error with code', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: 'C:/nonexistent/file.mp4' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBeTruthy()
    expect(error.message).toBeTruthy()
  })
})
