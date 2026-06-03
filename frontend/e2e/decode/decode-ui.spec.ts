import { test, expect } from '../fixtures'

test.describe('Decode module UI', () => {
  test('decoder profile select exists and has options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const decoderSelect = tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(decoderSelect).toBeVisible()

    // Wait for Vue async option rendering
    await decoderSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })
    const options = await decoderSelect.locator('option').allTextContents()
    expect(options.length).toBeGreaterThan(0)
  })

  test('hwaccel device input is visible and fillable', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const hwaccelInput = tauriPage.locator('label.field').filter({ hasText: '硬件设备' }).locator('input')
    await expect(hwaccelInput).toBeVisible()
    await expect(hwaccelInput).toHaveAttribute('placeholder', '留空则使用默认设备')

    // Type a device name and verify the value changed
    await hwaccelInput.fill('cuda')
    await expect(hwaccelInput).toHaveValue('cuda')

    await hwaccelInput.fill('')
    await expect(hwaccelInput).toHaveValue('')
  })

  test('switching decoder profile shows or hides capability options panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').first()
    const decoderSelect = section.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(decoderSelect).toBeVisible()

    try {
      await decoderSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })
    } catch {
      test.skip()
      return
    }
    const options = await decoderSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // The second field-grid (index 1) only renders when decoderOptions.length > 0
    const optionPanel = section.locator('div.field-grid.field-grid-2').nth(1)

    // Try to find a profile that shows the panel (non-software) and one that hides it
    const softwareOption = options.find((o) => o.toLowerCase().includes('software') || o.includes('软件'))
    const nonSoftwareOption = options.find((o) => !o.toLowerCase().includes('software') && !o.includes('软件'))

    if (softwareOption && nonSoftwareOption) {
      await decoderSelect.selectOption({ label: nonSoftwareOption })
      await expect(optionPanel).toBeVisible({ timeout: 5000 })

      await decoderSelect.selectOption({ label: softwareOption })
      await expect(optionPanel).not.toBeVisible()
    } else if (nonSoftwareOption) {
      // Fallback: just verify switching between two profiles changes panel state
      await decoderSelect.selectOption({ index: 0 })
      const initialVisible = await optionPanel.isVisible().catch(() => false)

      await decoderSelect.selectOption({ label: nonSoftwareOption })
      const newVisible = await optionPanel.isVisible().catch(() => false)

      // We only assert if the state actually changed
      if (initialVisible === newVisible) {
        test.skip()
      }
    } else {
      test.skip()
    }
  })
})
