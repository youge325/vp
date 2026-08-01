import { expect, test } from '../fixtures'
import { seedMediaItems, seedTaskConsoleState } from '../utils/media'
import { openModule } from '../utils/navigation'
import { saveE2EScreenshot } from '../utils/screenshots'
import type { TauriPage } from '../utils/wdio-tauri'

const renderControls = (tauriPage: TauriPage) => ({
  start: tauriPage.locator('.render-stack .panel-actions .primary-button'),
  pause: tauriPage.locator('.render-stack .panel-actions .ghost-button'),
  cancel: tauriPage.locator('.render-stack .panel-actions .danger-button'),
})

test.describe('Render module', () => {
  test('explains preflight blockers and enables start only for runnable media', async ({ tauriPage }) => {
    await openModule(tauriPage, '渲染', '批处理队列')
    const controls = renderControls(tauriPage)
    await expect(controls.start).toBeDisabled()
    await expect(tauriPage.locator('.start-blocked-hint')).toContainText('请先勾选要处理的素材')

    await seedMediaItems([{
      id: 'missing-output',
      displayName: 'missing-output.mp4',
      selected: true,
      outputDir: '',
    }])
    await expect(controls.start).toBeDisabled()
    await expect(tauriPage.locator('.start-blocked-hint')).toContainText('missing-output.mp4')
    await expect(tauriPage.locator('.start-blocked-hint')).toContainText('未填输出目录')

    await seedMediaItems([{
      id: 'ready',
      displayName: 'ready.mp4',
      selected: true,
      outputDir: 'C:/tmp/output',
    }])
    await expect(controls.start).toBeEnabled()
    await expect(tauriPage.locator('.start-blocked-hint')).not.toBeVisible()
  })

  test('locks both controls and exposes the pending operation label', async ({ tauriPage }) => {
    await openModule(tauriPage, '渲染', '批处理队列')
    const controls = renderControls(tauriPage)
    const pendingCases = [
      { pending: 'pause' as const, phase: 'running' as const, pauseLabel: '暂停中...', cancelLabel: '中断批次' },
      { pending: 'resume' as const, phase: 'paused' as const, pauseLabel: '继续中...', cancelLabel: '中断批次' },
      { pending: 'cancel' as const, phase: 'cancelling' as const, pauseLabel: '暂停队列', cancelLabel: '中断中...' },
    ]

    for (const item of pendingCases) {
      const ready = await seedTaskConsoleState({
        completedCount: 0,
        totalCount: 1,
        phase: item.phase,
        controlPending: item.pending,
      })
      expect(ready).toBe(true)
      await expect(controls.pause).toHaveText(item.pauseLabel)
      await expect(controls.cancel).toHaveText(item.cancelLabel)
      await expect(controls.pause).toBeDisabled()
      await expect(controls.cancel).toBeDisabled()
    }

    for (const state of [
      { phase: 'running' as const, screenshot: 'task-running' as const },
      { phase: 'paused' as const, screenshot: 'task-paused' as const },
      { phase: 'cancelling' as const, screenshot: 'task-cancelling' as const },
    ]) {
      await seedTaskConsoleState({
        completedCount: 0,
        totalCount: 1,
        phase: state.phase,
      })
      await saveE2EScreenshot(state.screenshot)
    }
  })

  test('renders logs, resume progress and a stable completed 100% state', async ({ tauriPage }) => {
    const ready = await seedTaskConsoleState({
      logs: ['恢复处理', '编码第 2 段'],
      completedCount: 1,
      totalCount: 2,
      phase: 'running',
      resumeStatus: {
        resumed: true,
        completedChunks: 3,
        completedOutputFrames: 150,
        totalOutputFrames: 300,
      },
    })
    expect(ready).toBe(true)
    await openModule(tauriPage, '渲染', '批处理队列')

    const console = tauriPage.locator('.task-console')
    await expect(console.locator('.log-line')).toHaveCount(2)
    await expect(console.locator('.log-panel')).toContainText('编码第 2 段')
    await expect(console.locator('.resume-banner')).toContainText('已完成 3 段')
    await expect(console.locator('.progress-label')).toHaveText('1 / 2')
    await expect(console.locator('.progress-fill')).toHaveAttribute('style', /width: 50%/)

    await seedTaskConsoleState({
      logs: ['任务完成'],
      completedCount: 2,
      totalCount: 2,
      phase: 'idle',
    })
    await expect(console.locator('.progress-label')).toHaveText('2 / 2')
    await expect(console.locator('.progress-fill')).toHaveAttribute('style', /width: 100%/)
    await expect(console.locator('.resume-banner')).not.toBeVisible()
  })
})
