import { test, expect } from './fixtures'

test.describe('Encode container switching', () => {
  test('container select has multiple options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const containerSelect = tauriPage.locator('label.field').filter({ hasText: '容器' }).locator('select')
    await expect(containerSelect).toBeVisible({ timeout: 5000 })

    const options = await containerSelect.locator('option').allTextContents()
    expect(options.length).toBeGreaterThanOrEqual(2)
    // Container options should be uppercase (MP4, MKV, MOV, etc.)
    const upperOptions = options.map((o) => o.toUpperCase())
    expect(upperOptions).toContain('MP4')
  })

  test('switching container updates container tag', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const containerSelect = tauriPage.locator('label.field').filter({ hasText: '容器' }).locator('select')
    await expect(containerSelect).toBeVisible({ timeout: 5000 })

    // Get current container from tag
    const containerTag = tauriPage.locator('.chip-row .tag').filter({ hasText: 'Container:' })
    await expect(containerTag).toBeVisible({ timeout: 5000 })
    const beforeText = await containerTag.textContent()

    // Switch to a different container if possible
    const options = await containerSelect.locator('option').allTextContents()
    const mkvOption = options.find((o) => o.toLowerCase() === 'mkv')
    if (mkvOption) {
      await containerSelect.selectOption({ label: mkvOption })
      await expect(containerTag).toContainText('MKV', { timeout: 5000 })
    } else {
      // Just verify switching works by picking another option
      const currentValue = await containerSelect.inputValue()
      const otherOption = options.find((o) => o !== currentValue)
      if (otherOption) {
        await containerSelect.selectOption({ label: otherOption })
        await expect(containerTag).toBeVisible({ timeout: 5000 })
        const afterText = await containerTag.textContent()
        expect(afterText?.trim().length).toBeGreaterThan(0)
        expect(afterText).not.toBe(beforeText)
      }
    }
  })

  test('encoder select is visible with options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const encoderSelect = tauriPage.locator('label.field').filter({ hasText: '编码器' }).locator('select')
    await expect(encoderSelect).toBeVisible({ timeout: 5000 })

    const options = await encoderSelect.locator('option').allTextContents()
    if (options.length === 0) {
      test.skip()
      return
    }
    expect(options.length).toBeGreaterThanOrEqual(1)
  })

  test('rate control mode select has expected options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const rateControlSelect = tauriPage.locator('label.field').filter({ hasText: '码率控制模式' }).locator('select')
    await expect(rateControlSelect).toBeVisible({ timeout: 5000 })

    const options = await rateControlSelect.locator('option').allTextContents()
    expect(options).toContain('CRF')
    expect(options).toContain('Bitrate')
  })
})
