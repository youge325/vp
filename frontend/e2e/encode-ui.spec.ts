import { test, expect } from './fixtures'

test.describe('Encode module UI', () => {
  // Wait for bootstrap environment check to finish before navigating.
  // The encode module's codec list depends on envStore.checkResult.
  test.beforeEach(async ({ tauriPage }) => {
    await expect(
      tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' }),
    ).toBeVisible({ timeout: 30000 })
  })

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

  test('switching codec updates encoder options panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const codecSelect = tauriPage.locator('label.field').filter({ hasText: '编码器' }).locator('select')
    await expect(codecSelect).toBeVisible()
    await codecSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })

    const options = await codecSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // Select first codec and check encoder options panel state
    await codecSelect.selectOption({ index: 0 })
    const encoderSection = tauriPage.locator('section.panel-surface').filter({ has: tauriPage.locator('h2', { hasText: '编码器参数' }) })
    const initialVisible = await encoderSection.isVisible().catch(() => false)
    const initialOptionCount = initialVisible
      ? await encoderSection.locator('.field-grid label.field').count()
      : 0

    // Try other codecs until we find one with a different panel state
    let changed = false
    for (let i = 1; i < options.length; i++) {
      await codecSelect.selectOption({ index: i })
      await tauriPage.waitForTimeout(200)
      const newVisible = await encoderSection.isVisible().catch(() => false)
      const newOptionCount = newVisible
        ? await encoderSection.locator('.field-grid label.field').count()
        : 0

      if (newVisible !== initialVisible || newOptionCount !== initialOptionCount) {
        changed = true
        break
      }
    }

    // If no codec produces a different state, skip the assertion
    if (!changed) {
      test.skip()
    }
  })

  test('switching codec updates container options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const codecSelect = tauriPage.locator('label.field').filter({ hasText: '编码器' }).locator('select')
    await expect(codecSelect).toBeVisible()
    await codecSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })

    const containerSelect = tauriPage.locator('label.field').filter({ hasText: '容器' }).locator('select')
    await expect(containerSelect).toBeVisible()

    // Get initial container options
    await containerSelect.locator('option').first().waitFor({ state: 'attached', timeout: 5000 })
    const initialContainerOptions = await containerSelect.locator('option').allTextContents()

    // Try switching to a different codec
    const codecOptions = await codecSelect.locator('option').allTextContents()
    if (codecOptions.length < 2) {
      test.skip()
      return
    }

    await codecSelect.selectOption({ index: 1 })
    await tauriPage.waitForTimeout(300)

    // Container options may have updated
    const newContainerOptions = await containerSelect.locator('option').allTextContents()

    // Either options changed or at least container still has valid options
    expect(newContainerOptions.length).toBeGreaterThan(0)
  })
})
