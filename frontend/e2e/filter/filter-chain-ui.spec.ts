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

test.describe('FilterChainEditor UI', () => {
  test('preprocess: add and remove a scale filter', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')

    // Add a scale filter
    const addSelect = section.locator('.filter-toolbar select')
    await expect(addSelect).toBeVisible()
    await addSelect.selectOption({ label: '缩放' })

    // Verify filter card appears
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })
    await expect(filterCard).toHaveCount(1)
    await expect(filterCard.locator('.filter-kind')).toHaveText('缩放')

    // Delete the filter
    const deleteButton = filterCard.locator('.filter-delete')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()

    // Verify empty state returns
    await expect(filterCard).not.toBeVisible()
    await expect(section.locator('.filter-empty')).toBeVisible()
  })

  test('postprocess: add and remove a denoise filter', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("后处理")')
    await expect(tauriPage.locator('h2:has-text("后处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '后处理')

    // Add a denoise filter
    const addSelect = section.locator('.filter-toolbar select')
    await expect(addSelect).toBeVisible()
    await addSelect.selectOption({ label: '降噪' })

    // Verify filter card appears
    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })
    await expect(filterCard).toHaveCount(1)
    await expect(filterCard.locator('.filter-kind')).toHaveText('降噪')

    // Delete the filter
    const deleteButton = filterCard.locator('.filter-delete')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()

    // Verify empty state returns
    await expect(filterCard).not.toBeVisible()
    await expect(section.locator('.filter-empty')).toBeVisible()
  })

  test('filter enable/disable toggle changes data-enabled attribute', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')

    // Add a sharpen filter
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '锐化' })

    const filterCard = section.locator('.filter-card')
    await expect(filterCard).toBeVisible({ timeout: 5000 })

    // Default: enabled
    await expect(filterCard).toHaveAttribute('data-enabled', 'true')

    // Disable
    const enableToggle = filterCard.locator('.filter-actions label.toggle-chip input[type="checkbox"]')
    await expect(enableToggle).toBeChecked()
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'false')
    await expect(enableToggle).not.toBeChecked()

    // Re-enable
    await enableToggle.click()
    await expect(filterCard).toHaveAttribute('data-enabled', 'true')
    await expect(enableToggle).toBeChecked()
  })

  test('adding multiple filters renders multiple cards', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')

    const addSelect = section.locator('.filter-toolbar select')

    // Add scale filter
    await addSelect.selectOption({ label: '缩放' })

    // Add crop filter
    await addSelect.selectOption({ label: '裁剪' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(2)

    // Verify order and kinds
    await expect(filterCards.nth(0).locator('.filter-kind')).toHaveText('缩放')
    await expect(filterCards.nth(1).locator('.filter-kind')).toHaveText('裁剪')

    // Both should be enabled by default
    await expect(filterCards.nth(0)).toHaveAttribute('data-enabled', 'true')
    await expect(filterCards.nth(1)).toHaveAttribute('data-enabled', 'true')

    // Delete first filter — second should remain
    await filterCards.nth(0).locator('.filter-delete').click()
    await expect(filterCards).toHaveCount(1)
    await expect(filterCards.nth(0).locator('.filter-kind')).toHaveText('裁剪')
  })
})
