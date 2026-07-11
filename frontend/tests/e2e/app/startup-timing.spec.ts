import { test, expect } from '../fixtures'

test.describe('App startup timing', () => {
  test('app shell renders within 15 seconds of Tauri launch', async ({ tauriPage }) => {
    // The fixture already waited for [data-testid="app-shell"] with 15s timeout.
    // If we reach this point, the app loaded successfully within the timeout.
    // Verify the shell is actually visible and interactive.
    await expect(tauriPage.locator('[data-testid="app-shell"]')).toBeVisible()
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible()

    // Verify key interactive elements exist
    const railLinks = tauriPage.locator('.rail-link')
    await expect(railLinks).toHaveCount(8)
  })
})
