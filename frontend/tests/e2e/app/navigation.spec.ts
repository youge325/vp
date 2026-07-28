import { test, expect } from '../fixtures'

test.describe('Module navigation', () => {
  test('navigates every production module and keeps the active rail state in sync', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })
    const routes = [
      { link: '输入', heading: '批量导入' },
      { link: '解码', heading: '解码设置' },
      { link: '预处理', heading: '预处理' },
      { link: '增强', heading: '增强流程' },
      { link: '后处理', heading: '后处理' },
      { link: '编码', heading: '编码与输出' },
      { link: '渲染', heading: '批处理队列' },
    ]

    for (const route of routes) {
      await tauriPage.click(`.rail-link:has-text("${route.link}")`)
      await expect(tauriPage.locator(`h2:has-text("${route.heading}")`)).toBeVisible({ timeout: 5000 })
      await expect(tauriPage.locator(`.rail-link:has-text("${route.link}")`)).toHaveClass(/active/)
    }

    await tauriPage.click('.rail-link:has-text("主页")')
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })
    await expect(tauriPage.locator('.topbar-title-row h1')).toHaveText('主页')
  })
})
