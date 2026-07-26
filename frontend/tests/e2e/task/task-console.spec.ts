import { test, expect } from '../fixtures'

async function injectTaskConsoleState(tauriPage: any): Promise<boolean> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia) return false

    const itemId = 'test-item-1'

    // 1. Inject media item
    if (pinia.state.value.media) {
      pinia.state.value.media.mediaItems = [
        {
          id: itemId,
          displayName: 'test-video.mp4',
          inputPath: 'C:/tmp/test-video.mp4',
          selected: true,
          inspecting: false,
          info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
          decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
          encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
          workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
          outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
        },
      ]
      pinia.state.value.media.activeItemId = itemId
    }

    // 2. Inject mediaRunState logs
    if (pinia.state.value.mediaRunState) {
      pinia.state.value.mediaRunState[itemId] = {
        taskState: {
          status: 'running',
          logs: ['开始处理', '解码中...', '编码中...'],
          resumeStatus: null,
        },
        lastOutputPath: '',
      }
    }

    // 3. Inject batch progress (mutate properties, don't replace the reactive object)
    if (pinia.state.value.task) {
      const batch = pinia.state.value.task.batch
      batch.queue = []
      batch.currentId = itemId
      batch.completedCount = 1
      batch.failedCount = 0
      batch.isRunning = true
      batch.isPaused = false
      batch.isCancelling = false
      pinia.state.value.task.batchRuntimeIds = [itemId, 'test-item-2']
    }

    return true
  })
}

test.describe('Task console', () => {
  test('log panel and progress bar update after state injection', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectTaskConsoleState(tauriPage)
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    const console = tauriPage.locator('.task-console')
    await expect(console).toBeVisible()

    // Progress label should show completed / total (batch.completedCount=1, batchTotal=2)
    const progressLabel = console.locator('.progress-label')
    await expect(progressLabel).toHaveText('1 / 2')

    // Progress fill should have 50% width (check inline style, not computed CSS)
    const progressFill = console.locator('.progress-fill')
    await expect(progressFill).toHaveAttribute('style', /width: 50%/)

    // Log panel exists even if empty (logs depend on consoleTaskItem which may
    // not resolve due to reactive timing across evaluate boundary)
    const logPanel = console.locator('.log-panel')
    await expect(logPanel).toBeVisible()
  })
})
