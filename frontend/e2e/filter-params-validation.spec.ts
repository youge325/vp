import { test, expect } from './fixtures'

async function enableSection(tauriPage: any, sectionTitle: string) {
  const section = tauriPage.locator('section.panel-surface').filter({
    has: tauriPage.locator('h2', { hasText: sectionTitle }),
  })
  const toggle = section.locator('.field-grid label.toggle-chip input[type="checkbox"]').first()
  await expect(toggle).toBeVisible()

  if (!(await toggle.isChecked())) {
    await toggle.click()
    await expect(toggle).toBeChecked()
  }

  return section
}

test.describe('Filter parameter validation and persistence', () => {
  test('sharpen amount input accepts decimal values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Find the amount input in the filter card body
    const amountInput = filterCard.locator('.filter-card-body input[type="number"]').first()
    await expect(amountInput).toBeVisible()

    // Clear and type a new decimal value
    await amountInput.fill('0.75')
    await amountInput.blur()

    // Verify the value was accepted
    await expect(amountInput).toHaveValue('0.75')
  })

  test('scale factor input accepts and retains values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Find the factor input
    const factorInput = filterCard.locator('.filter-card-body input[type="number"]').first()
    await expect(factorInput).toBeVisible()

    // Set a new value
    await factorInput.fill('1.5')
    await factorInput.blur()
    await expect(factorInput).toHaveValue('1.5')

    // Set another value
    await factorInput.fill('0.5')
    await factorInput.blur()
    await expect(factorInput).toHaveValue('0.5')
  })

  test('crop coordinate inputs accept integer values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '裁剪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Find all number inputs in the crop filter (x, y, width, height)
    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)

    // Set x coordinate
    await inputs.nth(0).fill('100')
    await inputs.nth(0).blur()
    await expect(inputs.nth(0)).toHaveValue('100')

    // Set y coordinate
    await inputs.nth(1).fill('200')
    await inputs.nth(1).blur()
    await expect(inputs.nth(1)).toHaveValue('200')
  })

  test('filter params persist after enable-disable toggle', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Modify the amount
    const amountInput = filterCard.locator('.filter-card-body input[type="number"]').first()
    await amountInput.fill('0.85')
    await amountInput.blur()
    await expect(amountInput).toHaveValue('0.85')

    // Disable the filter
    const enableToggle = filterCard.locator('.filter-actions label.toggle-chip input[type="checkbox"]')
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'false')

    // Re-enable the filter
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'true')

    // Verify the amount value persisted
    await expect(amountInput).toHaveValue('0.85')
  })
})
