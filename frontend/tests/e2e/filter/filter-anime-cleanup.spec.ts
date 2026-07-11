import { expect, test } from '../fixtures'

async function openCleanPreprocess(tauriPage: any) {
  await tauriPage.click('.rail-link:has-text("预处理")')
  await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

  const section = tauriPage.locator('section.panel-surface').filter({
    has: tauriPage.locator('h2', { hasText: '预处理' }),
  })
  const toggle = section.locator('.field-grid label.toggle-chip input[type="checkbox"]').first()
  if (!(await toggle.isChecked())) await toggle.click()
  while ((await section.locator('.filter-card').count()) > 0) {
    await section.locator('.filter-card').first().locator('.filter-delete').click()
  }
  return section
}

test.describe('Anime cleanup filter', () => {
  test('adds, edits, reorders, and retains Anime cleanup params', async ({ tauriPage }) => {
    const section = await openCleanPreprocess(tauriPage)
    const addSelect = section.locator('.filter-toolbar select')
    await addSelect.selectOption({ label: '缩放' })
    await addSelect.selectOption({ label: 'Anime 清理' })

    const cards = section.locator('.filter-card')
    await expect(cards).toHaveCount(2)
    const animeCard = cards.nth(1)
    await expect(animeCard.locator('.filter-kind')).toHaveText('Anime 清理')

    const profile = animeCard.locator('label.field').filter({ hasText: '预设' }).locator('select')
    const denoise = animeCard.locator('label.field').filter({ hasText: '降噪' }).locator('input')
    const edgeBoost = animeCard.locator('label.field').filter({ hasText: '边缘增强' }).locator('input')
    await expect(profile).toHaveValue('clean-lines')
    await expect(denoise).toHaveValue('15')
    await expect(edgeBoost).toHaveValue('30')

    await profile.selectOption('thin-outline')
    await expect(denoise).toHaveValue('8')
    await expect(edgeBoost).toHaveValue('45')
    await denoise.fill('12')
    await edgeBoost.fill('40')

    await animeCard.locator('.filter-actions button').nth(0).click()
    await expect(cards.nth(0).locator('.filter-kind')).toHaveText('Anime 清理')

    await tauriPage.click('.rail-link:has-text("后处理")')
    await tauriPage.click('.rail-link:has-text("预处理")')
    const retained = section.locator('.filter-card').nth(0)
    await expect(retained.locator('select')).toHaveValue('thin-outline')
    await expect(retained.locator('label.field').filter({ hasText: '降噪' }).locator('input')).toHaveValue('12')
    await expect(retained.locator('label.field').filter({ hasText: '边缘增强' }).locator('input')).toHaveValue('40')
  })
})
