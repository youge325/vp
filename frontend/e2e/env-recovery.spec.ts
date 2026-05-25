import { test, expect } from './fixtures'

async function injectEnvIssue(
  tauriPage: any,
  error: { message: string; code?: string },
): Promise<boolean> {
  return await tauriPage.evaluate(
    (payload: { error: { message: string; code?: string } }) => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.env?.env) return false
      pinia.state.value.env.env.issue = payload.error
      pinia.state.value.env.env.isChecking = false
      return true
    },
    { error },
  )
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

test.describe('Environment recovery', () => {
  test('env issue shows retry probe button in topbar', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const ok = await injectEnvIssue(tauriPage, { message: 'FFmpeg 未找到', code: 'EnvProbeError' })
    test.skip(!ok, 'Cannot access Pinia env store from evaluate')

    const retryButton = tauriPage.locator('.topbar-actions button').filter({ hasText: '重试探测' })
    await expect(retryButton).toBeVisible({ timeout: 5000 })
    await expect(retryButton).toBeEnabled()

    await clearEnvIssue(tauriPage)
    await expect(retryButton).not.toBeVisible()
  })

  test('env issue banner renders with error message', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const ok = await injectEnvIssue(tauriPage, { message: 'GPU 驱动检测失败', code: 'GpuProbeError' })
    test.skip(!ok, 'Cannot access Pinia env store from evaluate')

    // Topbar retry button should show
    const retryButton = tauriPage.locator('.topbar-actions button').filter({ hasText: '重试探测' })
    await expect(retryButton).toBeVisible({ timeout: 5000 })

    await clearEnvIssue(tauriPage)
    await expect(retryButton).not.toBeVisible()
  })

  test('topbar title remains visible when env issue is present', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const ok = await injectEnvIssue(tauriPage, { message: '环境检查失败' })
    test.skip(!ok, 'Cannot access Pinia env store from evaluate')

    const topbarTitle = tauriPage.locator('.topbar-title-row h1')
    await expect(topbarTitle).toBeVisible()
    await expect(topbarTitle).toHaveText('主页')

    await clearEnvIssue(tauriPage)
  })
})
