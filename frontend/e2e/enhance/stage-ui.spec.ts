import { test, expect } from '../fixtures'

test.describe('Stage module UI', () => {
  test('enabling preprocess toggle reveals filter section', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    // Locate the toggle inside a toggle-field label
    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '启用预处理' }).locator('input[type="checkbox"]')
    await expect(toggle).toBeVisible()

    // Ensure toggle is off before testing
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    // Filter section should not be visible yet
    const filterSection = tauriPage.locator('.filter-section')
    await expect(filterSection).not.toBeVisible()

    // Enable and verify filter section appears
    await toggle.click()
    await expect(toggle).toBeChecked()
    await expect(filterSection).toBeVisible({ timeout: 5000 })

    // Verify pipeline position caption is shown
    await expect(tauriPage.locator('.filter-section .panel-caption').filter({ hasText: '位于 解码 → 增强 之间' })).toBeVisible()
  })

  test('enabling postprocess toggle reveals filter section', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("后处理")')
    await expect(tauriPage.locator('h2:has-text("后处理")')).toBeVisible({ timeout: 5000 })

    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '启用后处理' }).locator('input[type="checkbox"]')
    await expect(toggle).toBeVisible()

    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    const filterSection = tauriPage.locator('.filter-section')
    await expect(filterSection).not.toBeVisible()

    await toggle.click()
    await expect(toggle).toBeChecked()
    await expect(filterSection).toBeVisible({ timeout: 5000 })

    await expect(tauriPage.locator('.filter-section .panel-caption').filter({ hasText: '位于 增强 → 编码 之间' })).toBeVisible()
  })
})
