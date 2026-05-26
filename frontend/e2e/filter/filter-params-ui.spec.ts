import { test, expect } from '../fixtures'

async function enablePreprocess(tauriPage: any) {
  const section = tauriPage.locator('section.panel-surface').filter({
    has: tauriPage.locator('h2', { hasText: '预处理' }),
  })
  const toggle = section.locator('.field-grid label.toggle-chip input[type="checkbox"]').first()
  await expect(toggle).toBeVisible()
  if (!(await toggle.isChecked())) {
    await toggle.click()
    await expect(toggle).toBeChecked()
  }
  return section
}

test.describe('Filter step parameter panels', () => {
  test('FilterScale mode switching toggles conditional fields', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enablePreprocess(tauriPage)

    // Add scale filter
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })

    const body = filterCard.locator('.filter-card-body')
    const fields = body.locator('.field')

    // Default mode is 'factor' → 3 fields: mode, interpolation, factor
    await expect(fields).toHaveCount(3)
    const modeSelect = fields.nth(0).locator('select')
    await expect(modeSelect).toHaveValue('factor')

    // Factor input (3rd field)
    const factorInput = fields.nth(2).locator('input')
    await expect(factorInput).toBeVisible()
    await expect(factorInput).toHaveAttribute('type', 'number')

    // Switch to resolution mode
    await modeSelect.selectOption({ label: '目标分辨率' })

    // Now 4 fields: mode, interpolation, width, height
    await expect(fields).toHaveCount(4)
    await expect(modeSelect).toHaveValue('resolution')

    const widthInput = fields.nth(2).locator('input')
    const heightInput = fields.nth(3).locator('input')
    await expect(widthInput).toBeVisible()
    await expect(widthInput).toHaveAttribute('type', 'number')
    await expect(heightInput).toBeVisible()
    await expect(heightInput).toHaveAttribute('type', 'number')

    // Switch back to factor
    await modeSelect.selectOption({ label: '缩放系数' })
    await expect(fields).toHaveCount(3)
    await expect(modeSelect).toHaveValue('factor')
  })

  test('FilterCrop coordinate inputs retain values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enablePreprocess(tauriPage)

    await section.locator('.filter-toolbar select').selectOption({ label: '裁剪' })
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })

    const fields = filterCard.locator('.filter-card-body .field')
    await expect(fields).toHaveCount(4)

    const xInput = fields.nth(0).locator('input')
    const yInput = fields.nth(1).locator('input')
    const wInput = fields.nth(2).locator('input')
    const hInput = fields.nth(3).locator('input')

    await xInput.fill('100')
    await yInput.fill('50')
    await wInput.fill('800')
    await hInput.fill('600')

    await expect(xInput).toHaveValue('100')
    await expect(yInput).toHaveValue('50')
    await expect(wInput).toHaveValue('800')
    await expect(hInput).toHaveValue('600')
  })

  test('FilterSharpen amount input updates value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enablePreprocess(tauriPage)

    await section.locator('.filter-toolbar select').selectOption({ label: '锐化' })
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })

    const fields = filterCard.locator('.filter-card-body .field')
    await expect(fields).toHaveCount(1)

    const amountInput = fields.nth(0).locator('input')
    await expect(amountInput).toHaveValue('0.5')

    await amountInput.fill('0.75')
    await expect(amountInput).toHaveValue('0.75')
  })

  test('FilterColor color adjustment inputs retain values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enablePreprocess(tauriPage)

    await section.locator('.filter-toolbar select').selectOption({ label: '色彩调整' })
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })

    const fields = filterCard.locator('.filter-card-body .field')
    await expect(fields).toHaveCount(3)

    const bInput = fields.nth(0).locator('input')
    const cInput = fields.nth(1).locator('input')
    const sInput = fields.nth(2).locator('input')

    await bInput.fill('0.2')
    await cInput.fill('1.5')
    await sInput.fill('1.2')

    await expect(bInput).toHaveValue('0.2')
    await expect(cInput).toHaveValue('1.5')
    await expect(sInput).toHaveValue('1.2')
  })
})
