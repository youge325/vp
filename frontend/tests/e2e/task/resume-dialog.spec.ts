import { test, expect } from '../fixtures'
import { clearResumeConflict, injectResumeConflict } from './resume-conflict-fixture'
import { openModule } from '../utils/navigation'

test.describe('Resume conflict dialog', () => {
  test('exposes accessible resume actions and closes after each decision', async ({ tauriPage }) => {
    await openModule(tauriPage, '渲染', '批处理队列')
    const descriptor = {
      kind: 'final_exists_with_resume' as const,
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    }
    const overlay = tauriPage.locator('.resume-conflict-overlay')
    for (const action of ['继续续传', '重新开始', '跳过此任务', '取消批次']) {
      const ready = await injectResumeConflict(tauriPage, descriptor)
      test.skip(!ready, 'Cannot seed resume conflict')
      await expect(overlay).toHaveAttribute('role', 'dialog')
      await expect(overlay).toHaveAttribute('aria-modal', 'true')
      await expect(overlay).toHaveAttribute('aria-labelledby')
      await expect(tauriPage.locator('.resume-conflict-title')).toHaveText('检测到先前进度')
      await expect(tauriPage.locator('.resume-conflict-message')).toContainText('3 段缓存')
      await tauriPage.locator('button', { hasText: action }).click()
      await expect(overlay).not.toBeVisible()
    }
  })

  test('renders overwrite mode and supports keyboard dismissal', async ({ tauriPage }) => {
    await openModule(tauriPage, '渲染', '批处理队列')
    const ready = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_only',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 0, completedOutputFrames: 0, totalOutputFrames: 0 },
    })
    test.skip(!ready, 'Cannot seed resume conflict')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(tauriPage.locator('.resume-conflict-title')).toHaveText('输出文件已存在')
    await expect(tauriPage.locator('.resume-conflict-message')).toContainText('C:/tmp/output.mp4')
    await expect(tauriPage.locator('button', { hasText: '覆盖' })).toBeVisible()
    await expect(tauriPage.locator('button', { hasText: '继续续传' })).not.toBeVisible()
    await tauriPage.keyboard.press('Escape')
    await expect(overlay).not.toBeVisible()
    await clearResumeConflict(tauriPage)
  })
})
