import { test, expect } from '../fixtures'

async function injectEncodeIssue(
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
      if (!pinia?.state?.value?.issue) return false
      pinia.state.value.issue.operationIssue = {
        scope: 'encode',
        error: payload.error,
      }
      return true
    },
    { error },
  )
}

async function clearEncodeIssue(tauriPage: any): Promise<void> {
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

test.describe('Output picker error handling', () => {
  test('encode issue banner renders on IO error', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const ok = await injectEncodeIssue(tauriPage, { message: '无法访问输出目录', code: 'IoError' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toHaveAttribute('role', 'alert')
    await expect(banner.locator('p')).toHaveText('无法访问输出目录')

    await clearEncodeIssue(tauriPage)
    await expect(banner).not.toBeVisible()
  })

  test('encode issue banner shows directory not found message', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const ok = await injectEncodeIssue(tauriPage, { message: 'D:/output 目录不存在或没有写入权限', code: 'PathNotFound' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner.locator('p')).toContainText('目录不存在')

    await clearEncodeIssue(tauriPage)
  })

  test('encode issue banner is absent on fresh instance', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).not.toBeVisible()
  })

  test('output dir input exists alongside error banner', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const ok = await injectEncodeIssue(tauriPage, { message: '权限不足' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    // Banner should be visible
    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })

    // Output dir input should still be present
    const outputInput = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')
    await expect(outputInput).toBeVisible()

    // Picker button should still be present
    const pickerButton = tauriPage.locator('.panel-actions .ghost-button').filter({ hasText: '选择输出目录' })
    await expect(pickerButton).toBeVisible()

    await clearEncodeIssue(tauriPage)
  })
})
