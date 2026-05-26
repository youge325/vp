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

test.describe('Filter pad parameters', () => {
  test('pad filter shows four coordinate inputs and color input', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '填充' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input')
    // 4 number inputs (top/bottom/left/right) + 1 text input (color)
    await expect(inputs).toHaveCount(5)

    // Verify each directional input exists
    const topInput = filterCard.locator('.filter-card-body label.field').nth(0).locator('input')
    await expect(topInput).toBeVisible()
    const bottomInput = filterCard.locator('.filter-card-body label.field').nth(1).locator('input')
    await expect(bottomInput).toBeVisible()
    const leftInput = filterCard.locator('.filter-card-body label.field').nth(2).locator('input')
    await expect(leftInput).toBeVisible()
    const rightInput = filterCard.locator('.filter-card-body label.field').nth(3).locator('input')
    await expect(rightInput).toBeVisible()

    // Color input
    const colorInput = filterCard.locator('.filter-card-body label.field').nth(4).locator('input')
    await expect(colorInput).toBeVisible()
    await expect(colorInput).toHaveAttribute('type', 'text')
  })

  test('pad inputs accept integer values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '填充' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const topInput = filterCard.locator('.filter-card-body label.field').nth(0).locator('input')
    await topInput.fill('10')
    await topInput.blur()
    await expect(topInput).toHaveValue('10')

    const bottomInput = filterCard.locator('.filter-card-body label.field').nth(1).locator('input')
    await bottomInput.fill('20')
    await bottomInput.blur()
    await expect(bottomInput).toHaveValue('20')

    const leftInput = filterCard.locator('.filter-card-body label.field').nth(2).locator('input')
    await leftInput.fill('30')
    await leftInput.blur()
    await expect(leftInput).toHaveValue('30')

    const rightInput = filterCard.locator('.filter-card-body label.field').nth(3).locator('input')
    await rightInput.fill('40')
    await rightInput.blur()
    await expect(rightInput).toHaveValue('40')
  })

  test('pad color input accepts hex values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '填充' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const colorInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^颜色/ }).locator('input')
    await expect(colorInput).toBeVisible()

    await colorInput.fill('#FF0000')
    await colorInput.blur()
    await expect(colorInput).toHaveValue('#FF0000')
  })

  test('pad filter default values are zero', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '填充' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const topInput = filterCard.locator('.filter-card-body label.field').nth(0).locator('input')
    await expect(topInput).toHaveValue('0')

    const bottomInput = filterCard.locator('.filter-card-body label.field').nth(1).locator('input')
    await expect(bottomInput).toHaveValue('0')

    const leftInput = filterCard.locator('.filter-card-body label.field').nth(2).locator('input')
    await expect(leftInput).toHaveValue('0')

    const rightInput = filterCard.locator('.filter-card-body label.field').nth(3).locator('input')
    await expect(rightInput).toHaveValue('0')

    const colorInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^颜色/ }).locator('input')
    await expect(colorInput).toHaveValue('#000000')
  })
})
