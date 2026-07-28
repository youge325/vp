import { expect, test } from '../fixtures'
import { addFilter, openEmptyFilterSection } from './helpers'

test.describe('Filter editor', () => {
  test('adds, reorders, disables and removes filters through the production UI', async ({ tauriPage }) => {
    const section = await openEmptyFilterSection(tauriPage)
    const scale = await addFilter(section, '缩放')
    const crop = await addFilter(section, '裁剪')
    const sharpen = await addFilter(section, '锐化')
    const cards = section.locator('.filter-card')

    await expect(cards).toHaveCount(3)
    await crop.locator('.filter-actions button').first().click()
    await expect(cards.nth(0).locator('.filter-kind')).toHaveText('裁剪')
    await expect(cards.nth(1).locator('.filter-kind')).toHaveText('缩放')

    const enabled = sharpen.locator('.filter-actions input[type="checkbox"]')
    await enabled.click()
    await expect(sharpen).toHaveAttribute('data-enabled', 'false')
    await enabled.click()
    await expect(sharpen).toHaveAttribute('data-enabled', 'true')

    while ((await cards.count()) > 0) {
      await cards.first().locator('.filter-delete').click()
    }
    await expect(section.locator('.filter-empty')).toContainText('尚未添加任何滤镜')
    await expect(scale).not.toBeVisible()
  })

  test('renders every filter kind and binds its editable controls', async ({ tauriPage }) => {
    const section = await openEmptyFilterSection(tauriPage)
    const kinds = ['缩放', '裁剪', '填充', '降噪', '锐化', '色彩调整']

    for (const kind of kinds) {
      const card = await addFilter(section, kind)
      await expect(card.locator('input, select')).toBeVisible()
    }

    const cards = section.locator('.filter-card')
    const scale = cards.nth(0)
    const mode = scale.locator('label.field').filter({ hasText: '模式' }).locator('select')
    await mode.selectOption({ label: '目标分辨率' })
    await expect(scale.locator('label.field').filter({ hasText: /^宽度$/ })).toBeVisible()
    await expect(scale.locator('label.field').filter({ hasText: /^高度$/ })).toBeVisible()
    await mode.selectOption({ label: '缩放系数' })
    await expect(scale.locator('label.field').filter({ hasText: /^缩放系数$/ })).toBeVisible()

    const cropInputs = cards.nth(1).locator('input[type="number"]')
    await expect(cropInputs).toHaveCount(4)
    await cropInputs.first().fill('24')
    await cropInputs.first().blur()
    await expect(cropInputs.first()).toHaveValue('24')

    const colorInputs = cards.nth(5).locator('input[type="number"]')
    await colorInputs.first().fill('0.25')
    await colorInputs.first().blur()
    await expect(colorInputs.first()).toHaveValue('0.25')
  })

  test('applies Anime cleanup presets and retains custom values across navigation', async ({ tauriPage }) => {
    const section = await openEmptyFilterSection(tauriPage)
    const card = await addFilter(section, 'Anime 清理')
    const profile = card.locator('label.field').filter({ hasText: '预设' }).locator('select')
    const denoise = card.locator('label.field').filter({ hasText: '降噪' }).locator('input')
    const edgeBoost = card.locator('label.field').filter({ hasText: '边缘增强' }).locator('input')

    await expect(profile).toHaveValue('clean-lines')
    await profile.selectOption('thin-outline')
    await expect(denoise).toHaveValue('8')
    await expect(edgeBoost).toHaveValue('45')
    await denoise.fill('12')
    await edgeBoost.fill('40')

    await tauriPage.click('.rail-link:has-text("后处理")')
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(card.locator('select')).toHaveValue('thin-outline')
    await expect(denoise).toHaveValue('12')
    await expect(edgeBoost).toHaveValue('40')
  })
})
