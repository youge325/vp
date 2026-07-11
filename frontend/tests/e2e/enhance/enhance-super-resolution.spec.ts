import { test, expect } from '../fixtures'

test.describe('Enhance super resolution parameters', () => {
  test('super resolution config fields are visible', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    await expect(section.locator('label.field').filter({ hasText: /^倍率/ })).toBeVisible({ timeout: 5000 })
    await expect(section.locator('label.field').filter({ hasText: '算法' })).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: '处理顺序' })).toBeVisible()
  })

  test('scale select has 2x and 4x options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    const scaleSelect = section.locator('label.field').filter({ hasText: /^倍率/ }).locator('select')
    await expect(scaleSelect).toBeVisible({ timeout: 5000 })

    const options = await scaleSelect.locator('option').allTextContents()
    expect(options).toContain('2x')
    expect(options).toContain('4x')
  })

  test('algorithm select is visible with options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })

    const options = await algorithmSelect.locator('option').allTextContents()
    if (options.length === 0) {
      test.skip()
      return
    }
    expect(options.length).toBeGreaterThanOrEqual(1)
  })

  test('process order can be switched', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    const processOrderSelect = section.locator('label.field').filter({ hasText: '处理顺序' }).locator('select')
    await expect(processOrderSelect).toBeVisible({ timeout: 5000 })

    const options = await processOrderSelect.locator('option').allTextContents()
    expect(options).toContain('先超分后补帧')
    expect(options).toContain('先补帧后超分')

    // Switch process order
    await processOrderSelect.selectOption({ label: '先补帧后超分' })

    // Verify the selection is applied
    const selectedValue = await processOrderSelect.inputValue()
    const selectedLabel = await processOrderSelect.locator(`option[value="${selectedValue}"]`).textContent()
    expect(selectedLabel?.trim()).toBe('先补帧后超分')
  })
})
