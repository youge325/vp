import { test, expect } from './fixtures'

function createMediaItem(id: string, displayName: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected: false,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264', audioCodec: 'aac', duration: 60, bitrate: 5000 },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
    workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
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

async function setBatchState(tauriPage: any, state: { isRunning: boolean; isPaused?: boolean; isCancelling?: boolean }): Promise<boolean> {
  return await tauriPage.evaluate((s) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.task?.batch) return false

    const batch = pinia.state.value.task.batch
    batch.isRunning = s.isRunning
    if (s.isPaused !== undefined) batch.isPaused = s.isPaused
    if (s.isCancelling !== undefined) batch.isCancelling = s.isCancelling
    return true
  }, state)
}

async function clearBatchState(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.task?.batch) {
        const batch = pinia.state.value.task.batch
        batch.isRunning = false
        batch.isPaused = false
        batch.isCancelling = false
        batch.completedCount = 0
        batch.failedCount = 0
        batch.currentId = null
        batch.queue = []
      }
    }
  })
}

test.describe('Preflight blocking conditions', () => {
  test('start button disabled with no selected items shows correct hint', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject media item but don't select it
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('preflight-1', 'video-a.mp4', { selected: false, outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 } }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Ensure batch is not running
    await clearBatchState(tauriPage)

    const startButton = tauriPage.locator('.render-stack .panel-actions .primary-button')
    const hint = tauriPage.locator('.render-stack .start-blocked-hint')

    await expect(startButton).toBeDisabled()
    await expect(hint).toBeVisible()
    await expect(hint).toContainText('请先勾选要处理的素材')

    // Clean up
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
  })

  test('start button disabled with missing outputDir shows item name in hint', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject media item with selected=true but empty outputDir
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('preflight-2', 'missing-output.mp4', {
        selected: true,
        outputConfig: { outputDir: '', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await clearBatchState(tauriPage)

    const startButton = tauriPage.locator('.render-stack .panel-actions .primary-button')
    const hint = tauriPage.locator('.render-stack .start-blocked-hint')

    await expect(startButton).toBeDisabled()
    await expect(hint).toBeVisible()
    await expect(hint).toContainText('missing-output.mp4')
    await expect(hint).toContainText('未填输出目录')

    // Clean up
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
  })

  test('start button enabled when all conditions met', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject media item with selected=true and valid outputDir
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('preflight-3', 'ready-video.mp4', {
        selected: true,
        outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await clearBatchState(tauriPage)

    const startButton = tauriPage.locator('.render-stack .panel-actions .primary-button')
    const hint = tauriPage.locator('.render-stack .start-blocked-hint')

    await expect(startButton).toBeEnabled()
    await expect(hint).not.toBeVisible()

    // Clean up
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
  })

  test('start button disabled when batch is running shows no hint', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject media item with all conditions met
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('preflight-4', 'running-video.mp4', {
        selected: true,
        outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Set batch running
    const batchOk = await setBatchState(tauriPage, { isRunning: true, isPaused: false, isCancelling: false })
    test.skip(!batchOk, 'Cannot access Pinia task store from evaluate')

    const startButton = tauriPage.locator('.render-stack .panel-actions .primary-button')
    const hint = tauriPage.locator('.render-stack .start-blocked-hint')

    // Button should be disabled
    await expect(startButton).toBeDisabled()
    // But no hint should be shown (reason is null when running)
    await expect(hint).not.toBeVisible()

    await clearBatchState(tauriPage)

    // Clean up
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
  })

  test('multiple items with one missing outputDir shows that item name', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject two items: first has outputDir, second doesn't
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('preflight-5', 'has-output.mp4', {
        selected: true,
        outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
      }),
      createMediaItem('preflight-6', 'no-output.mp4', {
        selected: true,
        outputConfig: { outputDir: '', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await clearBatchState(tauriPage)

    const hint = tauriPage.locator('.render-stack .start-blocked-hint')
    await expect(hint).toBeVisible()
    // The hint should mention the first item that is missing outputDir
    await expect(hint).toContainText('no-output.mp4')

    // Clean up
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
  })
})
