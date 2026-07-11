import { test, expect } from '../fixtures'

async function injectInputIssue(
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
        scope: 'input',
        error: payload.error,
      }
      return true
    },
    { error },
  )
}

async function clearInputIssue(tauriPage: any): Promise<void> {
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

test.describe('Import error handling', () => {
  test('input issue banner renders with correct title and message', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '无法读取文件信息', code: 'InspectError' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toHaveAttribute('role', 'alert')
    await expect(banner.locator('strong')).toHaveText('批量导入失败')
    await expect(banner.locator('p')).toHaveText('无法读取文件信息')

    await clearInputIssue(tauriPage)
    await expect(banner).not.toBeVisible()
  })

  test('input issue banner shows generic message when code is present', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '文件不存在或格式不支持', code: 'InvalidFile' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner.locator('p')).toContainText('文件不存在或格式不支持')

    await clearInputIssue(tauriPage)
  })

  test('input issue banner is not visible on fresh instance', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const banner = tauriPage.locator('.info-banner.info-banner-danger')
    await expect(banner).not.toBeVisible()
  })

  test('input issue banner class is danger variant', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '测试错误' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })
    // Should have danger class, not warning
    await expect(banner).toHaveClass(/info-banner-danger/)
    await expect(banner).not.toHaveClass(/info-banner-warning/)

    await clearInputIssue(tauriPage)
  })
})
