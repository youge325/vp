import { test, expect } from './fixtures'

test.describe('Decode module UI', () => {
  // Wait for bootstrap environment check — decoder profiles depend on envStore.checkResult.
  test.beforeEach(async ({ tauriPage }) => {
    await expect(
      tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' }),
    ).toBeVisible({ timeout: 30000 })
  })

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
})
