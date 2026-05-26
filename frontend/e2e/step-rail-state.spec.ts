import { test, expect } from './fixtures'

async function injectMediaItems(tauriPage: any, count: number): Promise<boolean> {
  return await tauriPage.evaluate((n: number) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.media) return false

    const items = Array.from({ length: n }, (_, i) => ({
      id: `rail-test-${i}`,
      displayName: `test-${i}.mp4`,
      inputPath: `C:/tmp/test-${i}.mp4`,
      selected: i === 0,
      inspecting: false,
      info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264', audioCodec: 'aac', duration: 60, bitrate: 5000 },
      decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
      encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
      workflowConfig: {
        fpsMode: 'multi',
        processOrder: 'super_resolution_then_interpolation',
        interpolation: { enabled: false, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
        superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
        anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
        preprocess: { enabled: false, filters: [] },
        postprocess: { enabled: false, filters: [] },
      },
      outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
    }))

    pinia.state.value.media.mediaItems = items
    if (!pinia.state.value.media.activeItemId && items.length > 0) {
      pinia.state.value.media.activeItemId = items[0].id
    }
    return true
  }, count)
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
        pinia.state.value.media.selectedIds = []
      }
    }
  })
}

async function enablePreprocess(tauriPage: any): Promise<boolean> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.preset) return false

    const preset = pinia.state.value.preset
    if (preset.draftPreset) {
      preset.draftPreset.workflowConfig.preprocess.enabled = true
    }
    return true
  })
}

test.describe('Step rail module states', () => {
  test('default module states have data-state attribute', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const railLinks = tauriPage.locator('.rail-link')
    const count = await railLinks.count()
    expect(count).toBeGreaterThanOrEqual(1)

    for (let i = 0; i < count; i++) {
      const link = railLinks.nth(i)
      const state = await link.getAttribute('data-state')
      expect(state).not.toBeNull()
      expect(['idle', 'ready', 'error']).toContain(state)
    }
  })

  test('input state becomes ready after injecting media items', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const inputLink = tauriPage.locator('.rail-link').filter({ hasText: '输入' })
    await expect(inputLink).toBeVisible()

    // Default state should be idle (no media items)
    const beforeState = await inputLink.getAttribute('data-state')
    expect(beforeState).toBe('idle')

    // Inject media items
    const ok = await injectMediaItems(tauriPage, 3)
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // State should become ready
    await expect(inputLink).toHaveAttribute('data-state', 'ready', { timeout: 5000 })

    await clearMediaItems(tauriPage)
  })

  test('preprocess state becomes ready after enabling preprocess', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const preprocessLink = tauriPage.locator('.rail-link').filter({ hasText: '预处理' })
    await expect(preprocessLink).toBeVisible()

    // Default state should be idle
    const beforeState = await preprocessLink.getAttribute('data-state')
    expect(beforeState).toBe('idle')

    // Enable preprocess via Pinia
    const ok = await enablePreprocess(tauriPage)
    test.skip(!ok, 'Cannot access Pinia preset store from evaluate')

    // State should become ready
    await expect(preprocessLink).toHaveAttribute('data-state', 'ready', { timeout: 5000 })
  })

  test('rail footer shows workflow and selection labels', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const footerChips = tauriPage.locator('.rail-footer .rail-footer-chip')
    const count = await footerChips.count()
    expect(count).toBeGreaterThanOrEqual(2)

    // First chip should be workflow label (default is '转码' since no stages enabled)
    const workflowChip = footerChips.nth(0)
    await expect(workflowChip).toBeVisible()
    const workflowText = await workflowChip.textContent()
    expect(workflowText?.trim().length).toBeGreaterThan(0)

    // Last chip should be task status
    const taskChip = footerChips.last()
    await expect(taskChip).toBeVisible()
    const taskText = await taskChip.textContent()
    expect(taskText?.trim()).toMatch(/任务/)
  })
})
