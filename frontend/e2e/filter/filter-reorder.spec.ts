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

test.describe('Filter chain reordering', () => {
  test('adding multiple filters renders in order', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: '裁剪' })
    await addSelect.selectOption({ label: '锐化' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(3)

    await expect(filterCards.nth(0).locator('.filter-kind')).toHaveText('缩放')
    await expect(filterCards.nth(1).locator('.filter-kind')).toHaveText('裁剪')
    await expect(filterCards.nth(2).locator('.filter-kind')).toHaveText('锐化')
  })

  test('move down button changes filter order', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: '裁剪' })
    await addSelect.selectOption({ label: '锐化' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(3)

    // Click down on the second filter (crop)
    const secondCard = filterCards.nth(1)
    const downButton = secondCard.locator('.filter-actions button').nth(1)
    await expect(downButton).toHaveText('↓')
    await downButton.click()

    // Order should now be: scale, sharpen, crop
    await expect(filterCards.nth(0).locator('.filter-kind')).toHaveText('缩放')
    await expect(filterCards.nth(1).locator('.filter-kind')).toHaveText('锐化')
    await expect(filterCards.nth(2).locator('.filter-kind')).toHaveText('裁剪')
  })

  test('move up button changes filter order', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: '裁剪' })
    await addSelect.selectOption({ label: '锐化' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(3)

    // Click up on the third filter (sharpen)
    const thirdCard = filterCards.nth(2)
    const upButton = thirdCard.locator('.filter-actions button').nth(0)
    await expect(upButton).toHaveText('↑')
    await upButton.click()

    // Order should now be: scale, sharpen, crop
    await expect(filterCards.nth(0).locator('.filter-kind')).toHaveText('缩放')
    await expect(filterCards.nth(1).locator('.filter-kind')).toHaveText('锐化')
    await expect(filterCards.nth(2).locator('.filter-kind')).toHaveText('裁剪')
  })

  test('first filter has disabled move-up button', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: '裁剪' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(2)

    const firstCard = filterCards.nth(0)
    const upButton = firstCard.locator('.filter-actions button').nth(0)
    await expect(upButton).toHaveText('↑')
    await expect(upButton).toBeDisabled()

    const downButton = firstCard.locator('.filter-actions button').nth(1)
    await expect(downButton).toHaveText('↓')
    await expect(downButton).toBeEnabled()
  })

  test('last filter has disabled move-down button', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const section = await enableSection(tauriPage, '预处理')
    const addSelect = section.locator('.filter-toolbar select')

    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: '裁剪' })

    const filterCards = section.locator('.filter-card')
    await expect(filterCards).toHaveCount(2)

    const lastCard = filterCards.nth(1)
    const upButton = lastCard.locator('.filter-actions button').nth(0)
    await expect(upButton).toHaveText('↑')
    await expect(upButton).toBeEnabled()

    const downButton = lastCard.locator('.filter-actions button').nth(1)
    await expect(downButton).toHaveText('↓')
    await expect(downButton).toBeDisabled()
  })
})
