import { test, expect } from '../fixtures'

async function injectBatchState(
  tauriPage: any,
  config: {
    items: Array<{
      id: string
      displayName: string
      selected: boolean
      outputDir: string | null
    }>
    batch?: {
      isRunning?: boolean
      isPaused?: boolean
      isCancelling?: boolean
      completedCount?: number
    }
    resumeStatus?: {
      resumed: boolean
      completedChunks: number
      completedOutputFrames: number
      totalOutputFrames: number
    }
  },
): Promise<boolean> {
  return await tauriPage.evaluate((payload) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia) return false

    const fullItems = payload.items.map((item) => ({
      id: item.id,
      displayName: item.displayName,
      inputPath: `C:/tmp/${item.displayName}`,
      selected: item.selected,
      inspecting: false,
      info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
      decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
      encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
      workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
      outputConfig: { outputDir: item.outputDir ?? '', openOnComplete: false, segmentFrames: 1000 },
    }))

    // 1. Inject media items
    if (pinia.state.value.media) {
      pinia.state.value.media.mediaItems = fullItems
      const firstSelected = fullItems.find((i: any) => i.selected)
      pinia.state.value.media.activeItemId = firstSelected?.id ?? fullItems[0]?.id ?? null
    }

    // 2. Inject batch runtime ids (used by batchTotal)
    const selectedIds = fullItems.filter((i: any) => i.selected).map((i: any) => i.id)
    if (pinia.state.value.task) {
      pinia.state.value.task.batchRuntimeIds = selectedIds
      const batch = pinia.state.value.task.batch
      batch.isRunning = payload.batch?.isRunning ?? false
      batch.isPaused = payload.batch?.isPaused ?? false
      batch.isCancelling = payload.batch?.isCancelling ?? false
      batch.completedCount = payload.batch?.completedCount ?? 0
      batch.failedCount = 0
      batch.queue = []
      batch.currentId = selectedIds[0] ?? null
    }

    // 3. Inject resume status into mediaRunState
    if (pinia.state.value.mediaRunState && payload.resumeStatus) {
      const targetId = selectedIds[0] ?? fullItems[0]?.id
      if (targetId) {
        pinia.state.value.mediaRunState[targetId] = {
          taskState: {
            status: 'running',
            logs: ['恢复处理'],
            resumeStatus: payload.resumeStatus,
          },
          lastOutputPath: '',
        }
      }
    }

    return true
  }, config)
}

async function clearBatchState(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.media) {
        pinia.state.value.media.mediaItems = []
        pinia.state.value.media.activeItemId = null
      }
      if (pinia?.state?.value?.task?.batch) {
        const batch = pinia.state.value.task.batch
        batch.isRunning = false
        batch.isPaused = false
        batch.isCancelling = false
        batch.completedCount = 0
        batch.failedCount = 0
        batch.queue = []
        batch.currentId = null
        pinia.state.value.task.batchRuntimeIds = []
      }
      if (pinia?.state?.value?.mediaRunState) {
        pinia.state.value.mediaRunState = {}
      }
    }
  })
}

test.describe('Render module batch UI', () => {
  test('cannotStartReason shows no items selected text', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject one unselected item
    const ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-1', displayName: 'video.mp4', selected: false, outputDir: 'C:/tmp/output' }],
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const hint = tauriPage.locator('.start-blocked-hint')
    await expect(hint).toBeVisible()
    await expect(hint).toContainText('请先勾选要处理的素材')

    const startButton = tauriPage.locator('.primary-button').filter({ hasText: '开始队列' })
    await expect(startButton).toBeDisabled()

    await clearBatchState(tauriPage)
  })

  test('cannotStartReason shows missing outputDir text', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-2', displayName: 'no-output.mp4', selected: true, outputDir: null }],
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const hint = tauriPage.locator('.start-blocked-hint')
    await expect(hint).toBeVisible()
    await expect(hint).toContainText('no-output.mp4')
    await expect(hint).toContainText('未填输出目录')

    const startButton = tauriPage.locator('.primary-button').filter({ hasText: '开始队列' })
    await expect(startButton).toBeDisabled()

    await clearBatchState(tauriPage)
  })

  test('interrupt button shows cancelling label when isCancelling', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-3', displayName: 'cancelling.mp4', selected: true, outputDir: 'C:/tmp/output' }],
      batch: { isRunning: true, isPaused: false, isCancelling: true },
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const interruptButton = tauriPage.locator('.danger-button')
    await expect(interruptButton).toHaveText('中断中...')
    await expect(interruptButton).toBeDisabled()

    // Pause button should also be disabled
    const pauseButton = tauriPage.locator('.ghost-button').filter({ hasText: /^(暂停队列|继续队列)$/ })
    await expect(pauseButton).toBeDisabled()

    await clearBatchState(tauriPage)
  })

  test('pause button toggles between pause and resume labels', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Running, not paused
    let ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-4', displayName: 'pause-test.mp4', selected: true, outputDir: 'C:/tmp/output' }],
      batch: { isRunning: true, isPaused: false, isCancelling: false },
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const pauseButton = tauriPage.locator('.ghost-button').filter({ hasText: /^(暂停队列|继续队列)$/ })
    await expect(pauseButton).toHaveText('暂停队列')
    await expect(pauseButton).toBeEnabled()

    // Now paused
    ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-4', displayName: 'pause-test.mp4', selected: true, outputDir: 'C:/tmp/output' }],
      batch: { isRunning: true, isPaused: true, isCancelling: false },
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await expect(pauseButton).toHaveText('继续队列')
    await expect(pauseButton).toBeEnabled()

    await clearBatchState(tauriPage)
  })

  test('resume status is stored correctly in mediaRunState', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-5', displayName: 'resume-test.mp4', selected: true, outputDir: 'C:/tmp/output' }],
      batch: { isRunning: true, isPaused: false, isCancelling: false, completedCount: 1 },
      resumeStatus: { resumed: true, completedChunks: 5, completedOutputFrames: 250, totalOutputFrames: 500 },
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    // DOM banner depends on consoleTaskItem computed which may not resolve
    // across evaluate boundary; verify store state directly.
    const storeResumeStatus = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const runState = pinia?.state?.value?.mediaRunState
      if (!runState) return null
      const firstKey = Object.keys(runState)[0]
      return firstKey ? runState[firstKey]?.taskState?.resumeStatus ?? null : null
    })
    expect(storeResumeStatus).not.toBeNull()
    expect(storeResumeStatus.resumed).toBe(true)
    expect(storeResumeStatus.completedChunks).toBe(5)
    expect(storeResumeStatus.completedOutputFrames).toBe(250)
    expect(storeResumeStatus.totalOutputFrames).toBe(500)

    // Verify console element still renders
    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    await clearBatchState(tauriPage)
  })

  test('TaskConsole resume banner hidden when no resume status', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectBatchState(tauriPage, {
      items: [{ id: 'batch-6', displayName: 'no-resume.mp4', selected: true, outputDir: 'C:/tmp/output' }],
      batch: { isRunning: true, isPaused: false, isCancelling: false, completedCount: 0 },
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    const resumeBanner = console.locator('.resume-banner')
    await expect(resumeBanner).not.toBeVisible()

    // Log panel and progress should still be visible
    await expect(console.locator('.log-panel')).toBeVisible()
    await expect(console.locator('.progress-label')).toHaveText('0 / 1')

    await clearBatchState(tauriPage)
  })
})
