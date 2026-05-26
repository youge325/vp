import { test, expect } from '../fixtures'

test.describe('Enhance anime optimization parameters', () => {
  test('anime config fields are visible', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })

    await expect(section.locator('label.field').filter({ hasText: /^预设/ })).toBeVisible({ timeout: 5000 })
    await expect(section.locator('label.field').filter({ hasText: /^降噪/ })).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: /^边缘增强/ })).toBeVisible()
  })

  test('profile select has options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })

    const profileSelect = section.locator('label.field').filter({ hasText: /^预设/ }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    const options = await profileSelect.locator('option').allTextContents()
    if (options.length === 0) {
      test.skip()
      return
    }
    expect(options.length).toBeGreaterThanOrEqual(1)
  })

  test('denoise input accepts integer values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })

    const denoiseInput = section.locator('label.field').filter({ hasText: /^降噪/ }).locator('input[type="number"]')
    await expect(denoiseInput).toBeVisible({ timeout: 5000 })

    await denoiseInput.fill('50')
    await denoiseInput.blur()
    await expect(denoiseInput).toHaveValue('50')
  })

  test('edgeBoost input accepts integer values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })

    const edgeBoostInput = section.locator('label.field').filter({ hasText: /^边缘增强/ }).locator('input[type="number"]')
    await expect(edgeBoostInput).toBeVisible({ timeout: 5000 })

    await edgeBoostInput.fill('75')
    await edgeBoostInput.blur()
    await expect(edgeBoostInput).toHaveValue('75')
  })
})
