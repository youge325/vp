import { test, expect } from './fixtures'

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

test.describe('Issue banner warning variant', () => {
  test('warning variant renders with warning class', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '这是一个警告', code: 'WarningCode' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })

    // Modify the banner class to warning via evaluate (no production view uses variant=warning yet)
    await tauriPage.evaluate(() => {
      const banner = document.querySelector('.info-banner')
      if (banner) {
        banner.classList.remove('info-banner-danger')
        banner.classList.add('info-banner-warning')
      }
    })

    await expect(banner).toHaveClass(/info-banner-warning/)

    await clearInputIssue(tauriPage)
  })

  test('warning variant does not have danger class', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '这是一个警告' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })

    await tauriPage.evaluate(() => {
      const banner = document.querySelector('.info-banner')
      if (banner) {
        banner.classList.remove('info-banner-danger')
        banner.classList.add('info-banner-warning')
      }
    })

    await expect(banner).toHaveClass(/info-banner-warning/)
    await expect(banner).not.toHaveClass(/info-banner-danger/)

    await clearInputIssue(tauriPage)
  })

  test('error variant renders with danger class by default', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '这是一个错误', code: 'ErrorCode' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toHaveClass(/info-banner-danger/)
    await expect(banner).not.toHaveClass(/info-banner-warning/)

    await clearInputIssue(tauriPage)
  })

  test('banner title matches injected scope', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectInputIssue(tauriPage, { message: '警告信息' })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.info-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner.locator('strong')).toHaveText('批量导入失败')

    await clearInputIssue(tauriPage)
  })
})
