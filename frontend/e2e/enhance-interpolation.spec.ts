import { test, expect } from './fixtures'

test.describe('Enhance interpolation parameters', () => {
  test('interpolation config fields are visible by default', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    // Interpolation is enabled by default; fields should be visible
    await expect(section.locator('label.field').filter({ hasText: '后端' })).toBeVisible({ timeout: 5000 })
    await expect(section.locator('label.field').filter({ hasText: '算法' })).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: '帧率模式' })).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: 'Scale' })).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: '精度' })).toBeVisible()
  })

  test('fpsMode target shows targetFps input and hides multi select', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    // Switch to target mode explicitly
    const fpsModeSelect = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    await expect(fpsModeSelect).toBeVisible({ timeout: 5000 })
    await fpsModeSelect.selectOption({ label: '目标 FPS' })

    // targetFps input should be visible
    const targetFpsField = section.locator('label.field').filter({ hasText: /^目标 FPS/ })
    await expect(targetFpsField).toBeVisible({ timeout: 5000 })
    const targetFpsInput = targetFpsField.locator('input[type="number"]')
    await expect(targetFpsInput).toBeVisible()

    // Multi select should be hidden
    const multiField = section.locator('label.field').filter({ hasText: /^倍率/ })
    await expect(multiField).not.toBeVisible()
  })

  test('fpsMode multi shows multi select and hides targetFps input', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    // Switch to multi mode
    const fpsModeSelect = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    await expect(fpsModeSelect).toBeVisible({ timeout: 5000 })
    await fpsModeSelect.selectOption({ label: '倍率' })

    // Multi select should be visible
    const multiField = section.locator('label.field').filter({ hasText: /^倍率/ })
    await expect(multiField).toBeVisible({ timeout: 5000 })
    const multiSelect = multiField.locator('select')
    await expect(multiSelect).toBeVisible()

    // targetFps input should be hidden
    const targetFpsField = section.locator('label.field').filter({ hasText: /^目标 FPS/ })
    await expect(targetFpsField).not.toBeVisible()
  })

  test('targetFps and scale inputs accept new values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    // Ensure target mode
    const fpsModeSelect = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    await expect(fpsModeSelect).toBeVisible({ timeout: 5000 })
    await fpsModeSelect.selectOption({ label: '目标 FPS' })

    // Modify targetFps
    const targetFpsInput = section.locator('label.field').filter({ hasText: /^目标 FPS/ }).locator('input[type="number"]')
    await expect(targetFpsInput).toBeVisible()
    await targetFpsInput.fill('120')
    await targetFpsInput.blur()
    await expect(targetFpsInput).toHaveValue('120')

    // Modify scale
    const scaleInput = section.locator('label.field').filter({ hasText: 'Scale' }).locator('input[type="number"]')
    await expect(scaleInput).toBeVisible()
    await scaleInput.fill('0.5')
    await scaleInput.blur()
    await expect(scaleInput).toHaveValue('0.5')
  })
})
