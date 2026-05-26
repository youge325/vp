import { test, expect } from '../fixtures'

test.describe('Module navigation', () => {
  test('clicking rail links navigates to different modules', async ({ tauriPage }) => {
    // 首页应显示 home-module
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // 点击 "输入" 模块
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // 点击 "编码" 模块
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // 点击 "渲染" 模块
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    // 回到主页
    await tauriPage.click('.rail-link:has-text("主页")')
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })
  })

  test('active rail link highlights current module', async ({ tauriPage }) => {
    // 默认首页激活
    const homeLink = tauriPage.locator('.rail-link:has-text("主页")')
    await expect(homeLink).toHaveClass(/active/)

    // 切换到渲染模块
    await tauriPage.click('.rail-link:has-text("渲染")')
    const renderLink = tauriPage.locator('.rail-link:has-text("渲染")')
    await expect(renderLink).toHaveClass(/active/)
    await expect(homeLink).not.toHaveClass(/active/)
  })

  test('all rail links navigate to their respective modules', async ({ tauriPage }) => {
    // Start from home
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
    }

    // Back to home
    await tauriPage.click('.rail-link:has-text("主页")')
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })
  })
})
