import { test, expect } from '../fixtures'

test.describe('Home module content', () => {
  test('environment stats and capability cards render after probe', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Wait for bootstrap environment check to complete
    await expect(
      tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' }),
    ).toBeVisible({ timeout: 30000 })

    // stats-grid should have 4 stat cards
    const statCards = tauriPage.locator('.stats-grid .stat-card')
    await expect(statCards).toHaveCount(4)

    // Each card should have a label and a non-empty value
    for (let i = 0; i < 4; i++) {
      const card = statCards.nth(i)
      await expect(card.locator('span').first()).toBeVisible()
      const valueText = await card.locator('strong').textContent()
      expect(valueText?.trim().length).toBeGreaterThan(0)
    }

    // chip-row tags: source, hwaccel, GPU, last probe time
    const chipTags = tauriPage.locator('.chip-row .tag')
    await expect(chipTags).toHaveCount(4)
    await expect(chipTags.nth(0)).toContainText('来源:')
    await expect(chipTags.nth(1)).toContainText('硬件加速:')
    await expect(chipTags.nth(2)).toContainText('GPU:')
    await expect(chipTags.nth(3)).toContainText('最近真实探测:')

    // familyCards encoding capability summary
    const summaryBlocks = tauriPage.locator('.summary-grid .summary-block')
    await expect(summaryBlocks.first()).toBeVisible()
    const summaryCount = await summaryBlocks.count()
    expect(summaryCount).toBeGreaterThan(0)

    for (let i = 0; i < summaryCount; i++) {
      const block = summaryBlocks.nth(i)
      await expect(block.locator('.summary-block-title')).toBeVisible()
      const value = await block.locator('.summary-line').textContent()
      expect(value?.trim().length).toBeGreaterThan(0)
    }
  })

  test('family cards have non-empty titles and values', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Wait for bootstrap environment check
    await expect(
      tauriPage.locator('.panel-actions button').filter({ hasText: '重新探测' }),
    ).toBeVisible({ timeout: 30000 })

    const summaryBlocks = tauriPage.locator('.summary-grid .summary-block')
    await expect(summaryBlocks.first()).toBeVisible()
    const count = await summaryBlocks.count()
    expect(count).toBeGreaterThan(0)

    for (let i = 0; i < count; i++) {
      const block = summaryBlocks.nth(i)
      const title = await block.locator('.summary-block-title').textContent()
      expect(title?.trim().length).toBeGreaterThan(0)
      const value = await block.locator('.summary-line').textContent()
      expect(value?.trim().length).toBeGreaterThan(0)
    }
  })
})
