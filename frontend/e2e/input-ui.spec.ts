import { test, expect } from './fixtures'

test.describe('Input module UI', () => {
  test('empty state and action buttons render correctly', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // Drop zone should be visible
    const dropzone = tauriPage.locator('.dropzone')
    await expect(dropzone).toBeVisible()
    await expect(dropzone).toContainText('拖放视频到这里')

    // Batch import button
    const importButton = tauriPage.locator('.panel-actions button.primary-button').filter({ hasText: '批量导入' })
    await expect(importButton).toBeVisible()
    await expect(importButton).toBeEnabled()

    // Select-all button (text depends on state, check both possibilities)
    const selectAllButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: /^(全选全部|取消全选)$/ })
    await expect(selectAllButton).toBeVisible()

    // Re-inspect button — disabled when no media items exist
    const reinspectButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: '重新读取' })
    await expect(reinspectButton).toBeVisible()
    await expect(reinspectButton).toBeDisabled()

    // Empty state in the media list section
    await expect(tauriPage.locator('.empty-state')).toBeVisible()
    await expect(tauriPage.locator('.empty-state')).toContainText('还没有素材')

    // Table should not be visible when empty
    await expect(tauriPage.locator('.table-wrap')).not.toBeVisible()
  })
})
