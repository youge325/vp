import { test, expect } from './fixtures'

async function injectEnvIssue(tauriPage: any): Promise<boolean> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.env) return false

    pinia.state.value.env.env.issue = {
      message: 'FFmpeg 未找到',
      code: 'EnvProbeError',
    }
    pinia.state.value.env.env.isChecking = false
    return true
  })
}

async function clearEnvIssue(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.env?.env) {
        pinia.state.value.env.env.issue = null
      }
    }
  })
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
      batch.currentId = 'shell-test-1'
    } else {
      batch.completedCount = 0
      batch.currentId = null
    }
    return true
  }, running)
}

test.describe('App shell', () => {
  test('topbar title updates when navigating between modules', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const topbarTitle = tauriPage.locator('.topbar-title-row h1')
    await expect(topbarTitle).toHaveText('主页')

    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(topbarTitle).toHaveText('编码')

    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(topbarTitle).toHaveText('增强')

    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(topbarTitle).toHaveText('渲染')

    await tauriPage.click('.rail-link:has-text("主页")')
    await expect(topbarTitle).toHaveText('主页')
  })

  test('retry probe button appears when env issue is injected', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // By default the button should not be visible (no issue)
    const retryButton = tauriPage.locator('.topbar-actions button').filter({ hasText: '重试探测' })
    await expect(retryButton).not.toBeVisible()

    // Inject an environment issue
    const ok = await injectEnvIssue(tauriPage)
    test.skip(!ok, 'Cannot access Pinia env store from evaluate')

    await expect(retryButton).toBeVisible({ timeout: 5000 })
    await expect(retryButton).toBeEnabled()

    // Clicking retry should trigger recheck — the button may briefly disappear
    // and reappear as checking starts/stops. Just verify it was clickable.
    await retryButton.click()

    await clearEnvIssue(tauriPage)
  })

  test('status pill reflects batch running state', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const statusPill = tauriPage.locator('.topbar-actions .status-pill')
    await expect(statusPill).toBeVisible()

    // Default idle state
    await expect(statusPill).toHaveAttribute('data-state', 'idle')

    // Set batch running
    const batchOk = await setBatchRunning(tauriPage, true)
    test.skip(!batchOk, 'Cannot access Pinia task store from evaluate')

    await expect(statusPill).toHaveAttribute('data-state', 'running')

    // Stop batch
    await setBatchRunning(tauriPage, false)
    await expect(statusPill).toHaveAttribute('data-state', 'idle')
  })
})
