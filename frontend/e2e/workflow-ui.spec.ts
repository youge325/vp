import { test, expect } from './fixtures'

test.describe('Workflow module UI', () => {
  test('enabling interpolation reveals interpolation config panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` to avoid matching the super-resolution section whose
    // "process order" option contains the substring "补帧".
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })
    // Use .first() — panel-head may contain multiple toggles (main enable + FP16)
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure interpolation is off before enabling (preset may have it on)
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const backendSelect = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible({ timeout: 5000 })

    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })
  })

  test('enabling superResolution reveals superResolution config panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` for precise section matching.
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure superResolution is off before enabling
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const scaleSelect = section.locator('label.field').filter({ hasText: '倍率' }).locator('select').first()
    await expect(scaleSelect).toBeVisible({ timeout: 5000 })

    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })
  })

  test('enabling anime reveals anime config fields', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` for precise section matching.
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure anime is off before enabling
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const profileSelect = section.locator('label.field').filter({ hasText: '预设' }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    const denoiseInput = section.locator('label.field').filter({ hasText: '降噪' }).locator('input')
    await expect(denoiseInput).toBeVisible({ timeout: 5000 })

    const edgeBoostInput = section.locator('label.field').filter({ hasText: '边缘增强' }).locator('input')
    await expect(edgeBoostInput).toBeVisible({ timeout: 5000 })
  })
})
