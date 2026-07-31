import { test, expect } from '../fixtures'
import { clearOperationIssue, setOperationIssue } from '../utils/pinia'
import { saveE2EScreenshot } from '../utils/screenshots'
import { openModule } from '../utils/navigation'
import { withPiniaState } from '../utils/wdio-tauri'

test.describe('Issue banner', () => {
  test('renders scoped input, encode and task failures in their production views', async ({ tauriPage }) => {
    const cases = [
      { scope: 'input' as const, rail: '输入', heading: '批量导入', title: '批量导入失败' },
      { scope: 'encode' as const, rail: '编码', heading: '编码与输出', title: '输出目录操作失败' },
      { scope: 'task' as const, rail: '渲染', heading: '批处理队列', title: '任务操作失败' },
    ]
    for (const item of cases) {
      await openModule(tauriPage, item.rail, item.heading)
      const ready = await setOperationIssue(item.scope, {
        message: `${item.scope} operation failed`,
        code: 'io_error',
      })
      test.skip(!ready, 'Cannot seed operation issue')
      const banner = tauriPage.locator('.info-banner-danger')
      await expect(banner).toHaveAttribute('role', 'alert')
      await expect(banner.locator('strong')).toHaveText(item.title)
      await expect(banner.locator('p')).toHaveText(`${item.scope} operation failed`)
      await clearOperationIssue()
      await expect(banner).not.toBeVisible()
    }
  })

  test('preset issue renders in the App shell global banner', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const ok = await setOperationIssue('preset', {
      message: '预设文件损坏，已恢复默认设置',
      code: 'schema_mismatch',
    })
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    const banner = tauriPage.locator('.global-issue-banner')
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toHaveAttribute('role', 'alert')
    await expect(banner.locator('strong')).toHaveText('预设持久化失败')
    await expect(banner.locator('p')).toHaveText('预设文件损坏，已恢复默认设置')

    await banner.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await saveE2EScreenshot('preset-banner')
    await clearOperationIssue()
    await expect(banner).not.toBeVisible()
  })

  test('keeps environment recovery actionable when probing fails', async ({ tauriPage }) => {
    const ready = await withPiniaState((state) => {
      const env = (state.env as { env?: Record<string, unknown> } | undefined)?.env
      if (!env) return false
      env.issue = { code: 'env_probe_error', message: 'FFmpeg 未找到' }
      env.isChecking = false
      return true
    })
    test.skip(!ready, 'Cannot seed environment issue')

    const retry = tauriPage.locator('.topbar-actions button', { hasText: '重试探测' })
    await expect(retry).toBeVisible()
    await expect(retry).toBeEnabled()
    await expect(tauriPage.locator('.topbar-title-row h1')).toHaveText('主页')
  })
})
