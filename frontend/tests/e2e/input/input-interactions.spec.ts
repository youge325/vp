import { test, expect } from '../fixtures'

function createMediaItem(id: string, displayName: string, selected: boolean = false) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
    workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
    outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
  }
}

async function injectMediaItems(tauriPage: any, items: unknown[]): Promise<boolean> {
  return await tauriPage.evaluate((data: unknown[]) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.media) return false

    pinia.state.value.media.mediaItems = data
    return true
  }, items)
}

async function clearMediaItems(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.media) {
        pinia.state.value.media.mediaItems = []
        pinia.state.value.media.activeItemId = null
      }
    }
  })
}

async function injectInputIssue(tauriPage: any, message: string): Promise<boolean> {
  return await tauriPage.evaluate((msg: string) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.issue) return false

    pinia.state.value.issue.operationIssue = {
      scope: 'input',
      error: { code: 'invalid_input', message: msg, details: null },
    }
    return true
  }, message)
}

async function clearInputIssue(tauriPage: any): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    if (vueApp) {
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (pinia?.state?.value?.issue) {
        pinia.state.value.issue.operationIssue = null
      }
    }
  })
}

test.describe('Input module interactions', () => {
  test('dropzone gains active class on dragover and loses it on dragleave', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const dropzone = tauriPage.locator('.dropzone')
    await expect(dropzone).toBeVisible()

    // Initially no active class
    await expect(dropzone).not.toHaveClass(/active/)

    // Trigger dragover
    await tauriPage.evaluate(() => {
      const dz = document.querySelector('.dropzone')
      if (dz) {
        dz.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true }))
      }
    })

    // Should have active class (dragActive = true)
    await expect(dropzone).toHaveClass(/active/)

    // Trigger dragleave
    await tauriPage.evaluate(() => {
      const dz = document.querySelector('.dropzone')
      if (dz) {
        dz.dispatchEvent(new DragEvent('dragleave', { bubbles: true, cancelable: true }))
      }
    })

    // Active class should be removed
    await expect(dropzone).not.toHaveClass(/active/)
  })

  test('reinspect button toggles enabled state based on media item presence', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const reinspectButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: '重新读取' })

    // No items: disabled
    await expect(reinspectButton).toBeDisabled()

    // Inject an item
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('reins-1', 'video-a.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })

    // With items: enabled
    await expect(reinspectButton).toBeEnabled()

    // Remove the item
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.media) {
          pinia.state.value.media.mediaItems = []
          pinia.state.value.media.activeItemId = null
        }
      }
    })

    // Back to disabled
    await expect(reinspectButton).toBeDisabled()
  })

  test('IssueBanner displays import failure message', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // No banner initially
    const banner = tauriPage.locator('.info-banner')
    await expect(banner).not.toBeVisible()

    // Inject an input issue
    const ok = await injectInputIssue(tauriPage, '无法读取文件：路径不存在或文件已损坏')
    test.skip(!ok, 'Cannot access Pinia issue store from evaluate')

    // Banner should be visible with the issue text
    await expect(banner).toBeVisible({ timeout: 5000 })
    await expect(banner).toContainText('批量导入失败')
    await expect(banner).toContainText('无法读取文件')

    // Clear the issue
    await clearInputIssue(tauriPage)
    await expect(banner).not.toBeVisible()
  })

  test('row click activates item while checkbox toggles selection independently', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('act-1', 'video-first.mp4', false),
      createMediaItem('act-2', 'video-second.mp4', false),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Set activeItemId to first item
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.media) {
          pinia.state.value.media.activeItemId = 'act-1'
        }
      }
    })

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const rows = tauriPage.locator('.media-row')
    await expect(rows).toHaveCount(2)

    // First row active, second not
    await expect(rows.nth(0)).toHaveClass(/active/)
    await expect(rows.nth(1)).not.toHaveClass(/active/)

    // Click checkbox on second row (does NOT change active item)
    const secondCheckbox = rows.nth(1).locator('input[type="checkbox"]')
    await secondCheckbox.click()

    // Second row selected but not active
    await expect(secondCheckbox).toBeChecked()
    await expect(rows.nth(0)).toHaveClass(/active/)
    await expect(rows.nth(1)).not.toHaveClass(/active/)

    // Click on second row body (not checkbox) to activate it
    await rows.nth(1).click()
    await expect(rows.nth(0)).not.toHaveClass(/active/)
    await expect(rows.nth(1)).toHaveClass(/active/)

    // First row checkbox still unchecked, second still checked
    await expect(rows.nth(0).locator('input[type="checkbox"]')).not.toBeChecked()
    await expect(rows.nth(1).locator('input[type="checkbox"]')).toBeChecked()

    await clearMediaItems(tauriPage)
  })
})
