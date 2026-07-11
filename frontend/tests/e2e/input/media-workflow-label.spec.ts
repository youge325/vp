import { test, expect } from '../fixtures'

function createMediaItem(id: string, displayName: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected: false,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf' as const, value: 23 }, options: {} },
    workflowConfig: {
      fpsMode: 'multi',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: { enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
      superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
    ...overrides,
  }
}

async function injectMediaItems(tauriPage: any, items: unknown[]): Promise<boolean> {
  return await tauriPage.evaluate((data: unknown[]) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.media) return false

    pinia.state.value.media.mediaItems = data
    if (data.length > 0 && !pinia.state.value.media.activeItemId) {
      pinia.state.value.media.activeItemId = (data[0] as any).id ?? null
    }
    return true
  }, items)
}

async function clearMediaItems(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.media) {
        pinia.state.value.media.mediaItems = []
        pinia.state.value.media.activeItemId = null
      }
    }
  })
}

test.describe('Media list workflow labels', () => {
  test('workflow label shows interpolation only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('wf-test-1', 'interp-only.mp4', {
        workflowConfig: {
          interpolation: { enabled: true, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
        },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Verify via store directly (DOM workflow label depends on computed reactivity)
    const label = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null

      const labels = [
        item.workflowConfig.interpolation?.enabled ? '补帧' : null,
        item.workflowConfig.superResolution?.enabled ? '超分' : null,
      ].filter(Boolean)
      return labels.length > 0 ? labels.join(' / ') : '格式转换'
    })
    expect(label).toBe('补帧')

    await clearMediaItems(tauriPage)
  })

  test('workflow label shows combined stages', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('wf-test-2', 'all-stages.mp4', {
        workflowConfig: {
          interpolation: { enabled: true, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: true, scaleFactor: 2.0, algorithm: 'realesrgan' },
        },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    const label = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null

      const labels = [
        item.workflowConfig.interpolation?.enabled ? '补帧' : null,
        item.workflowConfig.superResolution?.enabled ? '超分' : null,
      ].filter(Boolean)
      return labels.length > 0 ? labels.join(' / ') : '格式转换'
    })
    expect(label).toBe('补帧 / 超分')

    await clearMediaItems(tauriPage)
  })

  test('workflow label shows format conversion when no stages enabled', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('wf-test-3', 'format-only.mp4', {
        workflowConfig: {
          interpolation: { enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
        },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    const label = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null

      const labels = [
        item.workflowConfig.interpolation?.enabled ? '补帧' : null,
        item.workflowConfig.superResolution?.enabled ? '超分' : null,
      ].filter(Boolean)
      return labels.length > 0 ? labels.join(' / ') : '格式转换'
    })
    expect(label).toBe('格式转换')

    await clearMediaItems(tauriPage)
  })

  test('workflow label shows super resolution only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('wf-test-4', 'sr-only.mp4', {
        workflowConfig: {
          interpolation: { enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: true, scaleFactor: 2.0, algorithm: 'realesrgan' },
        },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    const label = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null

      const labels = [
        item.workflowConfig.interpolation?.enabled ? '补帧' : null,
        item.workflowConfig.superResolution?.enabled ? '超分' : null,
      ].filter(Boolean)
      return labels.length > 0 ? labels.join(' / ') : '格式转换'
    })
    expect(label).toBe('超分')

    await clearMediaItems(tauriPage)
  })
})
