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

test.describe('Filter crop parameters', () => {
  test('crop filter shows four coordinate inputs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '裁剪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    await expect(inputs).toHaveCount(4)

    const labels = filterCard.locator('.filter-card-body label.field')
    await expect(labels.nth(0)).toBeVisible()
    await expect(labels.nth(1)).toBeVisible()
    await expect(labels.nth(2)).toBeVisible()
    await expect(labels.nth(3)).toBeVisible()
  })

  test('crop inputs accept integer values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '裁剪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    await inputs.nth(0).fill('100')
    await inputs.nth(0).blur()
    await expect(inputs.nth(0)).toHaveValue('100')

    await inputs.nth(1).fill('200')
    await inputs.nth(1).blur()
    await expect(inputs.nth(1)).toHaveValue('200')

    await inputs.nth(2).fill('800')
    await inputs.nth(2).blur()
    await expect(inputs.nth(2)).toHaveValue('800')

    await inputs.nth(3).fill('600')
    await inputs.nth(3).blur()
    await expect(inputs.nth(3)).toHaveValue('600')
  })

  test('crop filter default values are correct', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '裁剪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    await expect(inputs.nth(0)).toHaveValue('0')  // x
    await expect(inputs.nth(1)).toHaveValue('0')  // y
    await expect(inputs.nth(2)).toHaveValue('1920') // width
    await expect(inputs.nth(3)).toHaveValue('1080') // height
  })

  test('crop inputs have correct min attributes', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '裁剪' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const inputs = filterCard.locator('.filter-card-body input[type="number"]')
    // x, y have min=0
    await expect(inputs.nth(0)).toHaveAttribute('min', '0')
    await expect(inputs.nth(1)).toHaveAttribute('min', '0')
    // width, height have min=1
    await expect(inputs.nth(2)).toHaveAttribute('min', '1')
    await expect(inputs.nth(3)).toHaveAttribute('min', '1')
  })
})
