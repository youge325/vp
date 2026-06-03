import { test, expect } from '../fixtures'
import type { TauriPage } from '../utils/wdio-tauri'

const waitForHomeProbe = async (tauriPage: TauriPage) => {
  await tauriPage.waitForFunction(() => {
    const hasProbeButton = Array.from(document.querySelectorAll('.panel-actions button'))
      .some((button) => (button.textContent ?? '').includes('重新探测'))
    return hasProbeButton
      && document.querySelectorAll('.stats-grid .stat-card').length === 4
      && document.querySelectorAll('.chip-row .tag').length === 4
  }, { timeout: 30000 })
}

const waitForSummaryBlocks = async (tauriPage: TauriPage) => {
  await tauriPage.waitForFunction(() => {
    const blocks = Array.from(document.querySelectorAll('.summary-grid .summary-block'))
    return blocks.length > 0 && blocks.every((block) => {
      const title = block.querySelector('.summary-block-title')?.textContent?.trim() ?? ''
      const value = block.querySelector('.summary-line')?.textContent?.trim() ?? ''
      return title.length > 0 && value.length > 0
    })
  }, { timeout: 30000 })

  return tauriPage.locator('.summary-grid .summary-block')
}

test.describe('Home module content', () => {
  test('environment stats and capability cards render after probe', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Wait for bootstrap environment check to complete
    await waitForHomeProbe(tauriPage)

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
    const summaryBlocks = await waitForSummaryBlocks(tauriPage)
    const summaryCount = await summaryBlocks.count()
    expect(summaryCount).toBeGreaterThan(0)

    for (let i = 0; i < summaryCount; i++) {
      const block = summaryBlocks.nth(i)
      await expect(block.locator('.summary-block-title')).toBeVisible()
      const value = await block.locator('.summary-line').textContent()
      expect(value?.trim().length).toBeGreaterThan(0)
    }
  })

})
