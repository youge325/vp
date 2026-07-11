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

  // Clean up any existing filter cards from previous tests
  while ((await section.locator('.filter-card').count()) > 0) {
    await section.locator('.filter-card').first().locator('.filter-delete').click()
  }

  return section
}

test.describe('Filter scale mode switching', () => {
  test('default mode shows factor input and hides resolution inputs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Factor input should be visible (use regex to avoid matching "模式" select options)
    const factorField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^缩放系数$/ })
    await expect(factorField).toBeVisible()
    const factorInput = factorField.locator('input[type="number"]')
    await expect(factorInput).toBeVisible()

    // Width/height inputs should not be visible
    const widthField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^宽度$/ })
    await expect(widthField).not.toBeVisible()
    const heightField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^高度$/ })
    await expect(heightField).not.toBeVisible()
  })

  test('switching to resolution mode shows width and height inputs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    // Switch mode to resolution
    const modeSelect = filterCard.locator('.filter-card-body label.field').filter({ hasText: '模式' }).locator('select')
    await expect(modeSelect).toBeVisible()
    await modeSelect.selectOption({ label: '目标分辨率' })

    // Width/height inputs should now be visible
    const widthField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^宽度$/ })
    await expect(widthField).toBeVisible({ timeout: 5000 })
    const heightField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^高度$/ })
    await expect(heightField).toBeVisible({ timeout: 5000 })

    // Factor input should be hidden
    const factorField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^缩放系数$/ })
    await expect(factorField).not.toBeVisible()
  })

  test('switching back to factor mode shows factor input again', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const modeSelect = filterCard.locator('.filter-card-body label.field').filter({ hasText: '模式' }).locator('select')
    await expect(modeSelect).toBeVisible()

    // Switch to resolution first
    await modeSelect.selectOption({ label: '目标分辨率' })
    await expect(filterCard.locator('.filter-card-body label.field').filter({ hasText: '宽度' })).toBeVisible({ timeout: 5000 })

    // Switch back to factor
    await modeSelect.selectOption({ label: '缩放系数' })

    // Factor input should be visible again
    const factorField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^缩放系数$/ })
    await expect(factorField).toBeVisible({ timeout: 5000 })

    // Width/height should be hidden
    const widthField = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^宽度$/ })
    await expect(widthField).not.toBeVisible()
  })

  test('factor input has correct step and min max attributes', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible()

    const factorInput = filterCard.locator('.filter-card-body label.field').filter({ hasText: /^缩放系数$/ }).locator('input[type="number"]')
    await expect(factorInput).toBeVisible()

    await expect(factorInput).toHaveAttribute('step', '0.01')
    await expect(factorInput).toHaveAttribute('min', '0.01')
    await expect(factorInput).toHaveAttribute('max', '10')
  })
})
