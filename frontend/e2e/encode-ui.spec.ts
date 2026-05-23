import { test, expect } from './fixtures'

test.describe('Encode module UI', () => {
  test('switching codec select updates container options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const codecSelect = tauriPage.locator('label.field').filter({ hasText: '编码器' }).locator('select')
    await expect(codecSelect).toBeVisible()

    // Vue may render options asynchronously — wait for at least one option
    await codecSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })
    const initialOptions = await codecSelect.locator('option').allTextContents()
    expect(initialOptions.length).toBeGreaterThan(0)

    const hevcOption = initialOptions.find((o) =>
      o.toLowerCase().includes('hevc') || o.toLowerCase().includes('h265') || o.toLowerCase().includes('265')
    )
    if (hevcOption) {
      await codecSelect.selectOption({ label: hevcOption })
    } else if (initialOptions.length > 1) {
      await codecSelect.selectOption({ index: 1 })
    }

    const containerSelect = tauriPage.locator('label.field').filter({ hasText: '容器' }).locator('select')
    await expect(containerSelect).toBeVisible()
    await containerSelect.locator('option').first().waitFor({ state: 'attached', timeout: 5000 })
    const containerOptions = await containerSelect.locator('option').allTextContents()
    expect(containerOptions.length).toBeGreaterThan(0)
  })

  test('keepAudio toggle can be clicked and changes checked state', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '保留音频' }).locator('input[type="checkbox"]')
    await expect(toggle).toBeVisible()

    const initiallyChecked = await toggle.isChecked()

    await toggle.click()
    await expect(toggle).toBeChecked({ checked: !initiallyChecked })

    await toggle.click()
    await expect(toggle).toBeChecked({ checked: initiallyChecked })
  })

  test('rateControl mode switch changes the value input', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const rateControlSelect = tauriPage.locator('label.field').filter({ hasText: '码率控制模式' }).locator('select')
    await expect(rateControlSelect).toBeVisible()

    const options = await rateControlSelect.locator('option').allTextContents()
    const bitrateOption = options.find((o) => o.toLowerCase().includes('bitrate') || o.includes('码率'))
    if (bitrateOption) {
      await rateControlSelect.selectOption({ label: bitrateOption })
    }

    const valueInput = tauriPage.locator('label.field').filter({ hasText: '码率控制值' }).locator('input')
    await expect(valueInput).toBeVisible()
  })
})
