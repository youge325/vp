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

test.describe('Filter sharpen parameters', () => {
  test('sharpen filter shows amount input', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const amountInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await expect(amountInput).toBeVisible()
  })

  test('sharpen amount accepts decimal values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const amountInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await amountInput.fill('0.75')
    await amountInput.blur()
    await expect(amountInput).toHaveValue('0.75')
  })

  test('sharpen filter default value is 0.5', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const amountInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await expect(amountInput).toHaveValue('0.5')
  })

  test('sharpen amount has correct step and min max attributes', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const amountInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^强度/ }).locator('input[type="number"]')
    await expect(amountInput).toHaveAttribute('step', '0.05')
    await expect(amountInput).toHaveAttribute('min', '0')
    await expect(amountInput).toHaveAttribute('max', '1')
  })
})
