import { test, expect } from '../fixtures'

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

test.describe('Filter denoise parameters', () => {
  test('denoise filter shows strength and color strength inputs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '降噪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    await expect(inputs).toHaveCount(2)

    const strengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await expect(strengthInput).toBeVisible()

    const colorStrengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^色彩强度/ }).locator('input[type="number"]')
    await expect(colorStrengthInput).toBeVisible()
  })

  test('denoise inputs accept new values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '降噪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const strengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await strengthInput.fill('15')
    await strengthInput.blur()
    await expect(strengthInput).toHaveValue('15')

    const colorStrengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^色彩强度/ }).locator('input[type="number"]')
    await colorStrengthInput.fill('12')
    await colorStrengthInput.blur()
    await expect(colorStrengthInput).toHaveValue('12')
  })

  test('denoise filter default values are correct', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '降噪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const strengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await expect(strengthInput).toHaveValue('10')

    const colorStrengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^色彩强度/ }).locator('input[type="number"]')
    await expect(colorStrengthInput).toHaveValue('10')
  })

  test('denoise filter values persist after enable-disable toggle', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '降噪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const strengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await strengthInput.fill('8')
    await strengthInput.blur()

    const colorStrengthInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^色彩强度/ }).locator('input[type="number"]')
    await colorStrengthInput.fill('6')
    await colorStrengthInput.blur()

    // Disable filter
    const enableToggle = filterCard.locator('.filter-actions label.toggle-chip input[type="checkbox"]')
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'false')

    // Re-enable
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'true')

    // Values should persist
    await expect(strengthInput).toHaveValue('8')
    await expect(colorStrengthInput).toHaveValue('6')
  })
})
