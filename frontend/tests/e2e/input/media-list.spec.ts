import { expect, test } from '../fixtures'
import { seedMediaItems } from '../utils/media'
import { openModule } from '../utils/navigation'

test.describe('Input media list', () => {
  test('renders the empty import surface and accepts drag lifecycle events', async ({ tauriPage }) => {
    await openModule(tauriPage, '输入', '批量导入')
    const dropzone = tauriPage.locator('.dropzone')
    const importButton = tauriPage.locator('.panel-actions .primary-button', { hasText: '批量导入' })

    await expect(dropzone).toContainText('拖放视频到这里')
    await expect(importButton).toBeEnabled()
    await expect(tauriPage.locator('.empty-state')).toContainText('还没有素材')
    await expect(tauriPage.locator('.table-wrap')).not.toBeVisible()

    await dropzone.evaluate((element) => {
      element.dispatchEvent(new DragEvent('dragover', { bubbles: true }))
    })
    await expect(dropzone).toHaveClass(/active/)
    await dropzone.evaluate((element) => {
      element.dispatchEvent(new DragEvent('dragleave', { bubbles: true }))
    })
    await expect(dropzone).not.toHaveClass(/active/)
  })

  test('shows production workflow labels for imported media fixtures', async ({ tauriPage }) => {
    const ready = await seedMediaItems([
      { id: 'format', displayName: 'format.mp4' },
      { id: 'interpolation', displayName: 'interpolation.mp4', interpolation: true },
      { id: 'super-resolution', displayName: 'super-resolution.mp4', superResolution: true },
      {
        id: 'combined',
        displayName: 'combined.mp4',
        interpolation: true,
        superResolution: true,
      },
    ])
    test.skip(!ready, 'Cannot seed media fixtures')
    await openModule(tauriPage, '输入', '批量导入')

    const rows = tauriPage.locator('.media-row')
    await expect(rows).toHaveCount(4)
    const workflowCell = (index: number) => rows.nth(index).locator('td').nth(5)
    await expect(workflowCell(0)).toHaveText('转码')
    await expect(workflowCell(1)).toHaveText('补帧')
    await expect(workflowCell(2)).toHaveText('超分')
    await expect(workflowCell(3)).toHaveText('补帧 / 超分')
  })

  test('selects, activates and removes rows through visible controls', async ({ tauriPage }) => {
    const ready = await seedMediaItems([
      { id: 'first', displayName: 'first.mp4' },
      { id: 'second', displayName: 'second.mp4' },
      { id: 'third', displayName: 'third.mp4' },
    ], 'first')
    test.skip(!ready, 'Cannot seed media fixtures')
    await openModule(tauriPage, '输入', '批量导入')

    const rows = tauriPage.locator('.media-row')
    await expect(rows.first()).toHaveClass(/active/)
    await rows.nth(1).click()
    await expect(rows.nth(1)).toHaveClass(/active/)

    const secondCheckbox = rows.nth(1).locator('input[type="checkbox"]')
    await secondCheckbox.click()
    await expect(secondCheckbox).toBeChecked()
    await expect(rows.nth(1)).toHaveClass(/active/)

    const selectAll = tauriPage.locator('.panel-actions .ghost-button', {
      hasText: /^(全选全部|取消全选)$/,
    })
    await selectAll.click()
    await expect(selectAll).toHaveText('取消全选')
    const checkboxes = rows.locator('input[type="checkbox"]')
    for (const checkbox of await checkboxes.all()) {
      await expect(checkbox).toBeChecked()
    }

    await rows.nth(1).locator('.table-action', { hasText: '移除' }).click()
    await expect(rows).toHaveCount(2)
    await expect(rows.nth(0).locator('.table-primary')).toHaveText('first.mp4')
    await expect(rows.nth(1).locator('.table-primary')).toHaveText('third.mp4')
  })
})
