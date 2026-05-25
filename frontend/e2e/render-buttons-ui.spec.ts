import { test, expect } from './fixtures'

async function injectMediaItem(tauriPage: any): Promise<boolean> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.media) return false

    const itemId = 'render-test-1'
    pinia.state.value.media.mediaItems = [
      {
        id: itemId,
        displayName: 'render-video.mp4',
        inputPath: 'C:/tmp/render-video.mp4',
        selected: true,
        inspecting: false,
        info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264', audioCodec: 'aac', duration: 60, bitrate: 5000 },
        decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
        encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
        workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
        outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
      },
    ]
    pinia.state.value.media.activeItemId = itemId
    return true
  })
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

test.describe('Render module button states', () => {
  test('Start button becomes enabled after injecting media with outputDir', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const startButton = tauriPage.locator('.render-stack .panel-actions .primary-button')
    const hint = tauriPage.locator('.render-stack .start-blocked-hint')

    // Fresh instance: no media, Start disabled with hint
    await expect(startButton).toBeDisabled()
    await expect(hint).toBeVisible()
    await expect(hint).toContainText('请先勾选要处理的素材')

    // Inject media item
    const ok = await injectMediaItem(tauriPage)
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Start should now be enabled
    await expect(startButton).toBeEnabled({ timeout: 5000 })
    await expect(hint).not.toBeVisible()
  })

  test('Pause button becomes enabled when batch is running', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const pauseButton = tauriPage.locator('.render-stack .panel-actions .ghost-button')

    // Fresh instance: not running, Pause disabled
    await expect(pauseButton).toBeDisabled()
    await expect(pauseButton).toHaveText('暂停队列')

    // Set batch running
    const ok = await setBatchState(tauriPage, { isRunning: true, isPaused: false, isCancelling: false })
    test.skip(!ok, 'Cannot access Pinia task store from evaluate')

    await expect(pauseButton).toBeEnabled({ timeout: 5000 })
    await expect(pauseButton).toHaveText('暂停队列')
  })

  test('Pause button label changes to "继续队列" when batch is paused', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const pauseButton = tauriPage.locator('.render-stack .panel-actions .ghost-button')

    // Set batch running
    const ok = await setBatchState(tauriPage, { isRunning: true, isPaused: false, isCancelling: false })
    test.skip(!ok, 'Cannot access Pinia task store from evaluate')
    await expect(pauseButton).toHaveText('暂停队列')

    // Set batch paused
    const paused = await setBatchState(tauriPage, { isRunning: true, isPaused: true, isCancelling: false })
    test.skip(!paused, 'Cannot access Pinia task store from evaluate')
    await expect(pauseButton).toHaveText('继续队列')
    await expect(pauseButton).toBeEnabled()
  })

  test('Interrupt button becomes enabled when batch is running', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const interruptButton = tauriPage.locator('.render-stack .panel-actions .danger-button')

    // Fresh instance: not running, Interrupt disabled
    await expect(interruptButton).toBeDisabled()
    await expect(interruptButton).toHaveText('中断批次')

    // Set batch running
    const ok = await setBatchState(tauriPage, { isRunning: true, isPaused: false, isCancelling: false })
    test.skip(!ok, 'Cannot access Pinia task store from evaluate')

    await expect(interruptButton).toBeEnabled({ timeout: 5000 })
    await expect(interruptButton).toHaveText('中断批次')
  })
})
