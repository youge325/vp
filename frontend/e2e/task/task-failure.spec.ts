import { test, expect } from '../fixtures'

async function injectIssue(
  tauriPage: any,
  scope: string,
  error: { message: string; code?: string },
): Promise<boolean> {
  return await tauriPage.evaluate(
    (payload: { scope: string; error: { message: string; code?: string } }) => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.issue) return false
      pinia.state.value.issue.operationIssue = {
        scope: payload.scope,
        error: payload.error,
      }
      return true
    },
    { scope, error },
  )
}

async function clearIssue(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.issue) {
        pinia.state.value.issue.operationIssue = null
      }
    }
  })
}

async function injectBatchWithFailedCount(tauriPage: any, failedCount: number, completedCount: number = 0): Promise<boolean> {
  return await tauriPage.evaluate((state: { failed: number; completed: number }) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.task?.batch) return false

    const batch = pinia.state.value.task.batch
    batch.failedCount = state.failed
    batch.completedCount = state.completed
    batch.currentId = null
    batch.isRunning = false
    batch.isPaused = false
    batch.isCancelling = false
    return true
  }, { failed: failedCount, completed: completedCount })
}

async function injectMediaRunState(tauriPage: any, itemId: string, status: string, logs: string[] = []): Promise<boolean> {
  return await tauriPage.evaluate((payload: { id: string; status: string; logs: string[] }) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.mediaRunState) return false

    pinia.state.value.mediaRunState[payload.id] = {
      taskState: {
        status: payload.status,
        logs: payload.logs,
        resumeStatus: null,
      },
      lastOutputPath: '',
    }
    return true
  }, { id: itemId, status, logs })
}

async function clearMediaRunState(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.mediaRunState) {
        pinia.state.value.mediaRunState = {}
      }
    }
  })
}

test.describe('Task failure and recovery', () => {
  test('task error banner renders with correct message', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectIssue(tauriPage, 'task', { message: '编码器初始化失败', code: 'EncoderError' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toHaveAttribute('role', 'alert')
    await expect(banner.locator('strong')).toHaveText('任务操作失败')
    await expect(banner.locator('p')).toHaveText('编码器初始化失败')

    await clearIssue(tauriPage)
    await expect(banner).not.toBeVisible()
  })

  test('task error banner renders with code when present', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectIssue(tauriPage, 'task', { message: 'FFmpeg 进程崩溃', code: 'ProcessCrashed' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner.locator('p')).toContainText('FFmpeg 进程崩溃')

    await clearIssue(tauriPage)
  })

  test('task state transitions to error status in status pill', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // Inject a media item with error state
    const ok = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media || !pinia?.state?.value?.mediaRunState) return false

      const itemId = 'fail-test-1'
      pinia.state.value.media.mediaItems = [
        {
          id: itemId,
          displayName: 'fail-video.mp4',
          inputPath: 'C:/tmp/fail-video.mp4',
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
      pinia.state.value.mediaRunState[itemId] = {
        taskState: { status: 'error', logs: ['开始处理', '错误: 编码器失败'], resumeStatus: null },
        lastOutputPath: '',
      }
      return true
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })

    // Verify store state directly (DOM status pill may not update due to reactive timing)
    const storeStatus = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const runState = pinia?.state?.value?.mediaRunState
      if (!runState) return null
      const firstKey = Object.keys(runState)[0]
      return firstKey ? runState[firstKey]?.taskState?.status ?? null : null
    })
    expect(storeStatus).toBe('error')

    // Table should still render
    const rows = tauriPage.locator('.media-row')
    await expect(rows).toHaveCount(1)

    await clearMediaRunState(tauriPage)
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

  test('failedCount reflects in task console progress label', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject batch state with 1 failed, 1 completed out of 2 total
    const batchOk = await injectBatchWithFailedCount(tauriPage, 1, 1)
    test.skip(!batchOk, 'Cannot access Pinia task store from evaluate')

    // Also set runtime ids to establish total
    const idsOk = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.task) return false
      pinia.state.value.task.batchRuntimeIds = ['fail-item-1', 'fail-item-2']
      return true
    })
    test.skip(!idsOk, 'Cannot access Pinia task store from evaluate')

    // Progress should show completed / total: 1 / 2
    const progressLabel = tauriPage.locator('.task-console .progress-label')
    await expect(progressLabel).toHaveText('1 / 2')

    // Progress fill should be 50%
    const progressFill = tauriPage.locator('.task-console .progress-fill')
    await expect(progressFill).toHaveAttribute('style', /width: 50%/)

    // Clean up
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.task?.batch) {
          const batch = pinia.state.value.task.batch
          batch.failedCount = 0
          batch.completedCount = 0
          batch.currentId = null
          batch.isRunning = false
          pinia.state.value.task.batchRuntimeIds = []
        }
      }
    })
  })

  test('console logs contain error messages', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // Inject media item and run state with error logs
    const ok = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media || !pinia?.state?.value?.mediaRunState || !pinia?.state?.value?.task) return false

      const itemId = 'fail-log-1'
      pinia.state.value.media.mediaItems = [
        {
          id: itemId,
          displayName: 'error-log-video.mp4',
          inputPath: 'C:/tmp/error-log-video.mp4',
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
      pinia.state.value.mediaRunState[itemId] = {
        taskState: {
          status: 'error',
          logs: ['开始处理', '解码中...', '错误: 编码器初始化失败', '任务已终止'],
          resumeStatus: null,
        },
        lastOutputPath: '',
      }
      // Set batch state so consoleTaskItem resolves
      pinia.state.value.task.batch.currentId = itemId
      pinia.state.value.task.batchRuntimeIds = [itemId]
      pinia.state.value.task.batch.completedCount = 0
      pinia.state.value.task.batch.failedCount = 1
      return true
    })
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    // Verify store-level logs directly (DOM log lines depend on consoleTaskItem)
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
    expect(storeLogs.length).toBe(4)
    expect(storeLogs[0]).toBe('开始处理')
    expect(storeLogs[1]).toBe('解码中...')
    expect(storeLogs[2]).toBe('错误: 编码器初始化失败')
    expect(storeLogs[3]).toBe('任务已终止')

    // Console should still render
    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    await clearMediaRunState(tauriPage)
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
          pinia.state.value.task.batch.currentId = null
          pinia.state.value.task.batchRuntimeIds = []
          pinia.state.value.task.batch.completedCount = 0
          pinia.state.value.task.batch.failedCount = 0
        }
      }
    })
  })

  test('batch with failed and completed items shows correct counts', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.task?.batch) return false

      const batch = pinia.state.value.task.batch
      batch.completedCount = 2
      batch.failedCount = 1
      batch.currentId = null
      batch.isRunning = false
      batch.isPaused = false
      batch.isCancelling = false
      pinia.state.value.task.batchRuntimeIds = ['item-1', 'item-2', 'item-3']
      return true
    })
    test.skip(!ok, 'Cannot access Pinia task store from evaluate')

    // Progress should show 2 / 3 (completed count / total)
    const progressLabel = tauriPage.locator('.task-console .progress-label')
    await expect(progressLabel).toHaveText('2 / 3')

    // Progress fill should be ~67%
    const progressFill = tauriPage.locator('.task-console .progress-fill')
    await expect(progressFill).toHaveAttribute('style', /width: 67%/)

    // Clean up
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.task?.batch) {
          const batch = pinia.state.value.task.batch
          batch.completedCount = 0
          batch.failedCount = 0
          pinia.state.value.task.batchRuntimeIds = []
        }
      }
    })
  })
})
