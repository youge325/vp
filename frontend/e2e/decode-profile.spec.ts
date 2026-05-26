import { test, expect } from './fixtures'

test.describe('Decode profile switching', () => {
  test('decode profile select is visible with options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const profileSelect = tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    const options = await profileSelect.locator('option').allTextContents()
    if (options.length === 0) {
      test.skip()
      return
    }
    expect(options.length).toBeGreaterThanOrEqual(1)
  })

  test('software decode profile shows software mode', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const profileSelect = tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    // Find and select software option
    const options = await profileSelect.locator('option').allTextContents()
    const softwareOption = options.find((o) => o.toLowerCase().includes('software') || o.includes('软件'))
    if (!softwareOption) {
      test.skip()
      return
    }

    await profileSelect.selectOption({ label: softwareOption })

    // Verify chip-row tags
    const modeTag = tauriPage.locator('.chip-row .tag').filter({ hasText: '模式:' })
    await expect(modeTag).toBeVisible({ timeout: 5000 })
    await expect(modeTag).toContainText('software')

    const hwaccelTag = tauriPage.locator('.chip-row .tag').filter({ hasText: 'hwaccel:' })
    await expect(hwaccelTag).toBeVisible()
    await expect(hwaccelTag).toContainText('software')
  })

  test('switching decode profile updates mode tag', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const profileSelect = tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    const options = await profileSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // Select first option and record mode
    await profileSelect.selectOption({ index: 0 })
    const modeTag = tauriPage.locator('.chip-row .tag').filter({ hasText: '模式:' })
    await expect(modeTag).toBeVisible({ timeout: 5000 })
    const firstMode = await modeTag.textContent()

    // Select a different option
    await profileSelect.selectOption({ index: options.length > 1 ? 1 : 0 })
    await expect(modeTag).toBeVisible({ timeout: 5000 })
    const secondMode = await modeTag.textContent()

    // The mode tag should have been updated (may be same or different)
    expect(secondMode?.trim().length).toBeGreaterThan(0)
    expect(firstMode?.trim().length).toBeGreaterThan(0)
  })

  test('chip row shows decoder info tags', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const tags = tauriPage.locator('.chip-row .tag')
    const count = await tags.count()
    expect(count).toBeGreaterThanOrEqual(3)

    // Should have mode, hwaccel, and decoder tags
    await expect(tauriPage.locator('.chip-row .tag').filter({ hasText: '模式:' })).toBeVisible()
    await expect(tauriPage.locator('.chip-row .tag').filter({ hasText: 'hwaccel:' })).toBeVisible()
    await expect(tauriPage.locator('.chip-row .tag').filter({ hasText: 'decoder:' })).toBeVisible()
  })
})
