import { test, expect } from '../fixtures'

test.describe('Environment check', () => {
  test('check_environment returns valid payload regardless of cache state', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    // source may be 'probe' (cache miss) or 'cache' (cache hit) depending on
    // prior test runs — all Tauri instances share the same app_data_dir.
    expect(['probe', 'cache']).toContain(result.source)
    expect(result.result).toHaveProperty('ffmpeg')
    expect(result.result.ffmpeg.available).toBe(true)
    expect(result.result).toHaveProperty('runtimeMode')
    expect(result.checkedAt).toBeTruthy()
  })

  test('second call returns source: cache', async ({ tauriPage }) => {
    // 第一次调用建立缓存
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment (first) failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    // 第二次调用应该命中缓存
    const result = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment (second) failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    expect(result.source).toBe('cache')
    expect(result.result.ffmpeg.available).toBe(true)
  })

  test('subsequent non-forced calls continue to use the cache', async ({ tauriPage }) => {
    // 先建立缓存
    await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment (cache seed) failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    // UI E2E 不强制刷新真实重资源探测；真实 probe 由 CLI smoke 覆盖。
    const result = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment (cached) failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    expect(result.source).toBe('cache')
    expect(result.result.ffmpeg.available).toBe(true)
  })
})
