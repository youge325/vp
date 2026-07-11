import { test, expect } from '../fixtures'

async function injectMediaItem(tauriPage: any): Promise<boolean> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.media) return false

    const itemId = 'rail-test-1'
    pinia.state.value.media.mediaItems = [
      {
        id: itemId,
        displayName: 'rail-test.mp4',
        inputPath: 'C:/tmp/rail-test.mp4',
        selected: false,
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

async function setWorkflowEnabled(tauriPage: any, config: { interpolation?: boolean; superResolution?: boolean; anime?: boolean }): Promise<boolean> {
  return await tauriPage.evaluate((cfg) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia) return false

    const apply = (wf: any) => {
      if (cfg.interpolation !== undefined) wf.interpolation.enabled = cfg.interpolation
      if (cfg.superResolution !== undefined) wf.superResolution.enabled = cfg.superResolution
      if (cfg.anime !== undefined) wf.anime.enabled = cfg.anime
    }

    const mediaStore = pinia._s?.get('media')
    const presetStore = pinia._s?.get('preset')
    const activeItem = mediaStore?.activeItem
    if (activeItem) {
      const next = structuredClone(activeItem.workflowConfig)
      apply(next)
      mediaStore.replaceItemConfig(activeItem.id, { workflowConfig: next })
      return true
    }

    if (!presetStore?.patchWorkflow) return false
    presetStore.patchWorkflow(apply)
    return true
  }, config)
}

async function setBatchRunning(tauriPage: any, running: boolean): Promise<boolean> {
  return await tauriPage.evaluate((isRunning) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.task) return false

    const batch = pinia.state.value.task.batch
    batch.isRunning = isRunning
    if (isRunning) {
      batch.completedCount = 1
      batch.currentId = 'rail-test-1'
    } else {
      batch.completedCount = 0
      batch.currentId = null
    }
    return true
  }, running)
}

test.describe('Step rail state', () => {
  test('input module state changes from idle to ready after media injection', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Initially no items — input should be idle
    const inputLink = tauriPage.locator('.rail-link').filter({ hasText: '输入' })
    await expect(inputLink.locator('.rail-state-dot')).toHaveAttribute('data-state', 'idle')

    // Inject a media item
    const ok = await injectMediaItem(tauriPage)
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Input should now be ready
    await expect(inputLink.locator('.rail-state-dot')).toHaveAttribute('data-state', 'ready')

    await clearMediaItems(tauriPage)
  })

  test('workflow label reflects enabled stages', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Default preset enables interpolation, so the workflow starts as "补帧".
    const footerChips = tauriPage.locator('.rail-footer-chip')
    const workflowChip = footerChips.first()
    await expect(workflowChip).toContainText('补帧')

    // Enable interpolation + superResolution
    const ok = await setWorkflowEnabled(tauriPage, { interpolation: true, superResolution: true })
    test.skip(!ok, 'Cannot access Pinia workbench editor from evaluate')

    await expect(workflowChip).toContainText('补帧 / 超分')

    // Reset to the default preset shape for later tests in this session.
    await setWorkflowEnabled(tauriPage, { interpolation: true, superResolution: false, anime: false })
  })

  test('task status label reflects batch running state', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Inject media item so batch can reference it
    const ok = await injectMediaItem(tauriPage)
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Default: idle (getTaskStatusLabel returns English labels)
    const taskChip = tauriPage.locator('.rail-footer-chip').filter({ hasText: /^任务/ })
    await expect(taskChip).toContainText('idle')

    // Set batch running
    const batchOk = await setBatchRunning(tauriPage, true)
    test.skip(!batchOk, 'Cannot access Pinia task store from evaluate')

    await expect(taskChip).toContainText('running')

    // Stop batch
    await setBatchRunning(tauriPage, false)
    await expect(taskChip).toContainText('idle')

    await clearMediaItems(tauriPage)
  })
})
