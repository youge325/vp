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

test.describe('Filter chain empty state', () => {
  test('empty state is visible when no filters are added', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')

    const emptyState = section.locator('.filter-empty')
    await expect(emptyState).toBeVisible()
    await expect(emptyState).toContainText('尚未添加任何滤镜')
  })

  test('adding first filter hides empty state', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')

    await expect(section.locator('.filter-empty')).toBeVisible()

    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })

    await expect(section.locator('.filter-empty')).not.toBeVisible()
    await expect(section.locator('.filter-card')).toBeVisible()
    await expect(section.locator('.filter-card')).toHaveCount(1)
  })

  test('deleting last filter shows empty state again', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    // Add a filter
    await addSelect.selectOption({ label: '缩放' })
    await expect(section.locator('.filter-card')).toHaveCount(1)
    await expect(section.locator('.filter-empty')).not.toBeVisible()

    // Delete the filter
    const deleteButton = section.locator('.filter-card').locator('.filter-delete')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()

    // Empty state should reappear
    await expect(section.locator('.filter-empty')).toBeVisible({ timeout: 5000 })
    await expect(section.locator('.filter-card')).not.toBeVisible()
  })

  test('empty state allows adding filter from dropdown', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("后处理")')
    await expect(tauriPage.locator('h2:has-text("后处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '后处理')

    // Verify empty state
    await expect(section.locator('.filter-empty')).toBeVisible()

    // Add filter from empty state
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '降噪' })

    await expect(section.locator('.filter-empty')).not.toBeVisible()
    await expect(section.locator('.filter-card')).toHaveCount(1)
    await expect(section.locator('.filter-card').locator('.filter-kind')).toHaveText('降噪')
  })
})
