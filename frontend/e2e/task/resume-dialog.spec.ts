import { test, expect } from '../fixtures'

// Minimal descriptor shape needed to mount the dialog
interface ResumeConflictDescriptor {
  kind: 'final_exists_with_resume' | 'final_exists_no_resume'
  outputPath: string
  inspection: {
    completedChunks: number
    completedOutputFrames: number
    totalOutputFrames: number
  }
}

async function injectConflict(
  tauriPage: any,
  descriptor: ResumeConflictDescriptor,
): Promise<boolean> {
  return await tauriPage.evaluate((d: ResumeConflictDescriptor) => {
    // Vue app is mounted on #app
    const root = document.querySelector('#app')
    if (!root) return false

    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false

    // Pinia stores state is at app.config.globalProperties.$pinia.state.value
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (pinia?.state?.value?.task) {
      pinia.state.value.task.pendingConflict = d
      return true
    }

    return false
  }, descriptor)
}

async function clearConflict(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.task) {
        pinia.state.value.task.pendingConflict = null
      }
    }
  })
}

test.describe('Resume conflict dialog', () => {
  test('resume mode renders correct title and buttons', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      inspection: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })
    await expect(overlay).toHaveAttribute('role', 'dialog')
    await expect(overlay).toHaveAttribute('aria-modal', 'true')

    await expect(tauriPage.locator('.resume-conflict-title')).toHaveText('检测到先前进度')
    await expect(tauriPage.locator('.resume-conflict-message')).toContainText('3 段缓存')

    await expect(tauriPage.locator('button').filter({ hasText: '继续续传' })).toBeVisible()
    await expect(tauriPage.locator('button').filter({ hasText: '重新开始' })).toBeVisible()
    await expect(tauriPage.locator('button').filter({ hasText: '跳过此任务' })).toBeVisible()
    await expect(tauriPage.locator('button').filter({ hasText: '取消批次' })).toBeVisible()

    // Dismiss via cancel button
    await tauriPage.locator('button').filter({ hasText: '取消批次' }).click()
    await expect(overlay).not.toBeVisible()

    await clearConflict(tauriPage)
  })

  test('overwrite mode renders correct title and buttons', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectConflict(tauriPage, {
      kind: 'final_exists_no_resume',
      outputPath: 'C:/tmp/output.mp4',
      inspection: { completedChunks: 0, completedOutputFrames: 0, totalOutputFrames: 0 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    await expect(tauriPage.locator('.resume-conflict-title')).toHaveText('输出文件已存在')
    await expect(tauriPage.locator('.resume-conflict-message')).toContainText('C:/tmp/output.mp4')

    await expect(tauriPage.locator('button').filter({ hasText: '覆盖' })).toBeVisible()
    await expect(tauriPage.locator('button').filter({ hasText: '跳过此任务' })).toBeVisible()
    await expect(tauriPage.locator('button').filter({ hasText: '取消批次' })).toBeVisible()

    // Dismiss via Escape key
    await tauriPage.keyboard.press('Escape')
    await expect(overlay).not.toBeVisible()

    await clearConflict(tauriPage)
  })
})
