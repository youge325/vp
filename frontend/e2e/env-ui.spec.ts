import { test, expect } from './fixtures'

test.describe('Environment module UI', () => {
  test('recheck button exists and is clickable', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const recheckButton = tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' })
    await expect(recheckButton).toBeVisible({ timeout: 10000 })

    // Button should be enabled (not disabled during loading)
    await expect(recheckButton).toBeEnabled()

    // Click recheck — it will trigger an async environment probe
    await recheckButton.click()

    // After click, button may briefly show loading state then return
    // Just verify the button comes back within a reasonable time
    await expect(recheckButton).toBeVisible({ timeout: 30000 })
    await expect(recheckButton).toBeEnabled()
  })
})
