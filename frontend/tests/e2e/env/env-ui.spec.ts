import { test, expect } from '../fixtures'
import { stubNextEnvironmentRecheckClick } from './helpers'

test.describe('Environment module UI', () => {
  test('recheck button exists and is clickable', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const recheckButton = tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' })
    await expect(recheckButton).toBeVisible({ timeout: 10000 })

    // Button should be enabled (not disabled during loading)
    await expect(recheckButton).toBeEnabled()

    const stubbed = await stubNextEnvironmentRecheckClick(tauriPage, '重新探测')
    test.skip(!stubbed, 'Cannot stub environment recheck click')

    // Click recheck — the click is stubbed here because real probe coverage
    // lives in CLI smoke tests and is too expensive for UI interaction tests.
    await recheckButton.click()

    await tauriPage.waitForFunction(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      const env = vueApp?.config?.globalProperties?.$pinia?.state?.value?.env?.env
      return Boolean(env && !env.isBootstrapping && !env.isChecking)
    }, { timeout: 5000 })

    const returnedButton = tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' })
    await expect(returnedButton).toBeVisible({ timeout: 5000 })
    await expect(returnedButton).toBeEnabled()
  })
})
