import { browser } from '@wdio/globals'
import { test, expect } from '../fixtures'
import { saveE2EScreenshot } from '../utils/screenshots'
import type { TauriPage } from '../utils/wdio-tauri'

interface RailLayout {
  linkCount: number
  railBottom: number
  renderBottom: number
  footerBottom: number
  clientHeight: number
  scrollHeight: number
}

const readRailLayout = async (tauriPage: TauriPage): Promise<RailLayout> => {
  return await tauriPage.evaluate(() => {
    const rail = document.querySelector<HTMLElement>('.rail-column')
    const links = [...document.querySelectorAll<HTMLElement>('.rail-link')]
    const renderLink = links.at(-1)
    const footer = document.querySelector<HTMLElement>('.rail-footer')
    if (!rail || !renderLink || !footer) {
      throw new Error('Step rail layout is incomplete')
    }

    const railRect = rail.getBoundingClientRect()
    return {
      linkCount: links.length,
      railBottom: railRect.bottom,
      renderBottom: renderLink.getBoundingClientRect().bottom,
      footerBottom: footer.getBoundingClientRect().bottom,
      clientHeight: rail.clientHeight,
      scrollHeight: rail.scrollHeight,
    }
  })
}

const waitForRailLayout = async (tauriPage: TauriPage): Promise<void> => {
  await tauriPage.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  }))
}

const expectRailToFit = (layout: RailLayout): void => {
  expect(layout.linkCount).toBe(8)
  expect(layout.renderBottom <= layout.railBottom + 0.5).toBe(true)
  expect(layout.footerBottom <= layout.railBottom + 0.5).toBe(true)
  expect(layout.scrollHeight <= layout.clientHeight + 1).toBe(true)
}

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

  test('keeps every rail card visible without scrolling at desktop and minimum window sizes', async ({ tauriPage }) => {
    const originalSize = await browser.getWindowSize()
    const sizes = [
      { width: 1280, height: 860 },
      { width: 1040, height: 760 },
    ]

    try {
      for (const size of sizes) {
        await browser.setWindowSize(size.width, size.height)
        await waitForRailLayout(tauriPage)
        await tauriPage.click('.rail-link:has-text("渲染")')
        await expect(tauriPage.locator('.rail-link:has-text("渲染")')).toHaveClass(/active/)
        expectRailToFit(await readRailLayout(tauriPage))
      }

      await saveE2EScreenshot('navigation-rail')
    } finally {
      await browser.setWindowSize(originalSize.width, originalSize.height)
      await waitForRailLayout(tauriPage)
    }
  })
})
