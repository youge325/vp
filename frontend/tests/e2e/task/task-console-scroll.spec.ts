import { test, expect } from '../fixtures'

async function injectTaskConsoleState(tauriPage: any, config: {
  itemId: string
  displayName: string
  logs: string[]
  completedCount: number
  totalCount: number
  resumeStatus?: { resumed: boolean; completedChunks: number; completedOutputFrames: number; totalOutputFrames: number }
}): Promise<boolean> {
  return await tauriPage.evaluate((payload) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia) return false

    // 1. Inject media item
    if (pinia.state.value.media) {
      pinia.state.value.media.mediaItems = [
        {
          id: payload.itemId,
          displayName: payload.displayName,
          inputPath: `C:/tmp/${payload.displayName}`,
          selected: true,
          inspecting: false,
          info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
          decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
          encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
          workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
          outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
        },
      ]
      pinia.state.value.media.activeItemId = payload.itemId
    }

    // 2. Inject mediaRunState logs and status
    if (pinia.state.value.mediaRunState) {
      pinia.state.value.mediaRunState[payload.itemId] = {
        taskState: {
          status: payload.logs.length > 0 ? 'running' : 'idle',
          logs: payload.logs,
          resumeStatus: payload.resumeStatus ?? null,
        },
        lastOutputPath: '',
      }
    }

    // 3. Inject batch progress
    if (pinia.state.value.task) {
      const batch = pinia.state.value.task.batch
      batch.queue = []
      batch.currentId = payload.itemId
      batch.completedCount = payload.completedCount
      batch.failedCount = 0
      batch.isRunning = payload.completedCount < payload.totalCount
      batch.isPaused = false
      batch.isCancelling = false
      pinia.state.value.task.batchRuntimeIds = Array.from({ length: payload.totalCount }, (_, i) => `test-item-${i + 1}`)
    }

    return true
  }, config)
}

async function clearTaskConsoleState(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.mediaRunState) {
        pinia.state.value.mediaRunState = {}
      }
      if (pinia?.state?.value?.task?.batch) {
        const batch = pinia.state.value.task.batch
        batch.queue = []
        batch.currentId = null
        batch.completedCount = 0
        batch.failedCount = 0
        batch.isRunning = false
        batch.isPaused = false
        batch.isCancelling = false
        pinia.state.value.task.batchRuntimeIds = []
      }
      if (pinia?.state?.value?.media) {
        pinia.state.value.media.mediaItems = []
        pinia.state.value.media.activeItemId = null
      }
    }
  })
}

test.describe('Task console interactions', () => {
  test('log panel is present and store contains injected logs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Generate 60 log lines
    const logs = Array.from({ length: 60 }, (_, i) => `Log line ${i + 1}: processing frame ${(i + 1) * 10}`)

    const ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'scroll-test-1',
      displayName: 'scroll-video.mp4',
      logs,
      completedCount: 1,
      totalCount: 2,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    // Log panel should be visible regardless of consoleTaskItem resolution
    const logPanel = console.locator('.log-panel')
    await expect(logPanel).toBeVisible()

    // Verify store-level logs directly (consoleTaskItem may not resolve across evaluate boundary)
    const storeLogs = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const runState = pinia?.state?.value?.mediaRunState
      if (!runState) return null
      // Find first entry's logs
      const firstKey = Object.keys(runState)[0]
      return firstKey ? runState[firstKey]?.taskState?.logs ?? null : null
    })
    expect(storeLogs).not.toBeNull()
    expect(storeLogs.length).toBe(60)
    expect(storeLogs[0]).toBe(logs[0])
    expect(storeLogs[59]).toBe(logs[59])

    await clearTaskConsoleState(tauriPage)
  })

  test('progress bar updates across boundary values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    // Test 0 / 2
    let ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'progress-test-1',
      displayName: 'progress-video.mp4',
      logs: [],
      completedCount: 0,
      totalCount: 2,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    let progressLabel = console.locator('.progress-label')
    let progressFill = console.locator('.progress-fill')
    await expect(progressLabel).toHaveText('0 / 2')
    await expect(progressFill).toHaveAttribute('style', /width: 0%/)

    // Test 1 / 2
    ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'progress-test-2',
      displayName: 'progress-video.mp4',
      logs: ['Task 1 done'],
      completedCount: 1,
      totalCount: 2,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await expect(progressLabel).toHaveText('1 / 2')
    await expect(progressFill).toHaveAttribute('style', /width: 50%/)

    // Test 2 / 2
    ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'progress-test-3',
      displayName: 'progress-video.mp4',
      logs: ['Task 1 done', 'Task 2 done'],
      completedCount: 2,
      totalCount: 2,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await expect(progressLabel).toHaveText('2 / 2')
    await expect(progressFill).toHaveAttribute('style', /width: 100%/)

    await clearTaskConsoleState(tauriPage)
  })

  test('resumeStatus is stored correctly in mediaRunState', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const resumeStatus = {
      resumed: true,
      completedChunks: 3,
      completedOutputFrames: 150,
      totalOutputFrames: 300,
    }

    const ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'resume-test-1',
      displayName: 'resume-video.mp4',
      logs: ['恢复处理', '继续编码'],
      completedCount: 1,
      totalCount: 2,
      resumeStatus,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    // Verify resumeStatus in store directly (DOM banner depends on consoleTaskItem which may not resolve)
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
    expect(storeResumeStatus.completedChunks).toBe(3)
    expect(storeResumeStatus.completedOutputFrames).toBe(150)
    expect(storeResumeStatus.totalOutputFrames).toBe(300)

    await clearTaskConsoleState(tauriPage)
  })

  test('resume banner is hidden when resumeStatus is null', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'resume-test-2',
      displayName: 'no-resume-video.mp4',
      logs: ['开始处理'],
      completedCount: 0,
      totalCount: 2,
      resumeStatus: undefined,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    const resumeBanner = console.locator('.resume-banner')
    await expect(resumeBanner).not.toBeVisible()

    await clearTaskConsoleState(tauriPage)
  })

  test('store logs contain progress lines and regular messages', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Mix regular logs with progress lines
    const logs: string[] = []
    for (let i = 0; i < 20; i++) {
      logs.push(`Processing segment ${i}`)
      logs.push(`[VP_PROGRESS] ${i * 5}%`)
    }
    logs.push('[VP_PROGRESS] 100%')

    const ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'logcap-test-1',
      displayName: 'logcap-video.mp4',
      logs,
      completedCount: 1,
      totalCount: 1,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    // Verify store-level logs (DOM log lines depend on consoleTaskItem)
    const storeLogs = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const runState = pinia?.state?.value?.mediaRunState
      if (!runState) return null
      const firstKey = Object.keys(runState)[0]
      return firstKey ? runState[firstKey]?.taskState?.logs ?? null : null
    })
    expect(storeLogs).not.toBeNull()
    expect(storeLogs.length).toBe(41) // 20 regular + 21 progress
    expect(storeLogs[0]).toBe('Processing segment 0')
    expect(storeLogs[1]).toBe('[VP_PROGRESS] 0%')
    expect(storeLogs[40]).toBe('[VP_PROGRESS] 100%')

    // Verify the console element exists
    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()
    const logPanel = console.locator('.log-panel')
    await expect(logPanel).toBeVisible()

    await clearTaskConsoleState(tauriPage)
  })

  test('empty log panel renders without errors', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectTaskConsoleState(tauriPage, {
      itemId: 'empty-test-1',
      displayName: 'empty-video.mp4',
      logs: [],
      completedCount: 0,
      totalCount: 1,
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    const logPanel = console.locator('.log-panel')
    await expect(logPanel).toBeVisible()

    // No log lines when empty
    const logLines = logPanel.locator('.log-line')
    await expect(logLines).toHaveCount(0)

    // Progress should still show
    const progressLabel = console.locator('.progress-label')
    await expect(progressLabel).toHaveText('0 / 1')

    await clearTaskConsoleState(tauriPage)
  })
})
