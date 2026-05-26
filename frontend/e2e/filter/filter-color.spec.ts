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

test.describe('Filter color adjustments', () => {
  test('color filter inputs accept new values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '色彩调整' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Modify brightness
    const brightnessInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^亮度/ }).locator('input[type="number"]')
    await brightnessInput.fill('0.5')
    await brightnessInput.blur()
    await expect(brightnessInput).toHaveValue('0.5')

    // Modify contrast
    const contrastInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^对比度/ }).locator('input[type="number"]')
    await contrastInput.fill('1.5')
    await contrastInput.blur()
    await expect(contrastInput).toHaveValue('1.5')

    // Modify saturation
    const saturationInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^饱和度/ }).locator('input[type="number"]')
    await saturationInput.fill('2')
    await saturationInput.blur()
    await expect(saturationInput).toHaveValue('2')
  })

  test('color filter default values are correct', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '色彩调整' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const brightnessInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^亮度/ }).locator('input[type="number"]')
    await expect(brightnessInput).toHaveValue('0')

    const contrastInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^对比度/ }).locator('input[type="number"]')
    await expect(contrastInput).toHaveValue('1')

    const saturationInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^饱和度/ }).locator('input[type="number"]')
    await expect(saturationInput).toHaveValue('1')
  })

  test('color filter inputs have correct type and attributes', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '色彩调整' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const brightnessInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^亮度/ }).locator('input[type="number"]')
    await expect(brightnessInput).toHaveAttribute('step', '0.05')
    await expect(brightnessInput).toHaveAttribute('min', '-1')
    await expect(brightnessInput).toHaveAttribute('max', '1')

    const contrastInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^对比度/ }).locator('input[type="number"]')
    await expect(contrastInput).toHaveAttribute('step', '0.05')
    await expect(contrastInput).toHaveAttribute('min', '0')
    await expect(contrastInput).toHaveAttribute('max', '3')
  })

  test('color filter values persist after enable-disable toggle', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '色彩调整' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Set values
    const brightnessInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^亮度/ }).locator('input[type="number"]')
    await brightnessInput.fill('0.3')
    await brightnessInput.blur()

    const contrastInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^对比度/ }).locator('input[type="number"]')
    await contrastInput.fill('1.2')
    await contrastInput.blur()

    // Disable filter
    const enableToggle = filterCard.locator('.filter-actions label.toggle-chip input[type="checkbox"]')
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'false')

    // Re-enable
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'true')

    // Values should persist
    await expect(brightnessInput).toHaveValue('0.3')
    await expect(contrastInput).toHaveValue('1.2')
  })
})
