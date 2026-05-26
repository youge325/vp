import { test, expect } from '../fixtures'

function createMediaItem(id: string, displayName: string, inputPath: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath,
    selected: false,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264', audioCodec: 'aac', duration: 60, bitrate: 5000 },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
    workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
    outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
    ...overrides,
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
    if (data.length > 0 && !pinia.state.value.media.activeItemId) {
      pinia.state.value.media.activeItemId = (data[0] as any).id ?? null
    }
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

test.describe('Media selection and activation', () => {
  test('active row highlights and clicking a row changes active item', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('sel-test-1', 'video-a.mp4', 'C:/tmp/video-a.mp4'),
      createMediaItem('sel-test-2', 'video-b.mp4', 'C:/tmp/video-b.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const rows = tauriPage.locator('.media-row')
    await expect(rows).toHaveCount(2)

    // First row is active by default
    await expect(rows.nth(0)).toHaveClass(/active/)
    await expect(rows.nth(1)).not.toHaveClass(/active/)

    // Click second row
    await rows.nth(1).click()
    await expect(rows.nth(0)).not.toHaveClass(/active/)
    await expect(rows.nth(1)).toHaveClass(/active/)

    // Verify activeItemId changed via store
    const activeId = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.media?.activeItemId ?? null
    })
    expect(activeId).toBe('sel-test-2')

    await clearMediaItems(tauriPage)
  })

  test('checkbox toggles selection without changing active item', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('sel-test-3', 'video-c.mp4', 'C:/tmp/video-c.mp4'),
      createMediaItem('sel-test-4', 'video-d.mp4', 'C:/tmp/video-d.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const rows = tauriPage.locator('.media-row')
    const firstCheckbox = rows.nth(0).locator('input[type="checkbox"]')

    // First row is active by default
    await expect(rows.nth(0)).toHaveClass(/active/)

    // Click checkbox on second row (stop propagation on the td)
    const secondCheckbox = rows.nth(1).locator('input[type="checkbox"]')
    await secondCheckbox.click()

    // Second row should be selected but not active
    await expect(secondCheckbox).toBeChecked()
    await expect(rows.nth(0)).toHaveClass(/active/)
    await expect(rows.nth(1)).not.toHaveClass(/active/)

    // Verify selectedIds via store
    const selectedIds = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (!vueApp) return []
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.media?.mediaItems
        ?.filter((item: any) => item.selected)
        ?.map((item: any) => item.id) ?? []
    })
    expect(selectedIds).toContain('sel-test-4')
    expect(selectedIds).not.toContain('sel-test-3')

    // First checkbox should not be checked
    await expect(firstCheckbox).not.toBeChecked()

    await clearMediaItems(tauriPage)
  })

  test('select-all button text changes with multiple items', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('sel-test-5', 'video-e.mp4', 'C:/tmp/video-e.mp4'),
      createMediaItem('sel-test-6', 'video-f.mp4', 'C:/tmp/video-f.mp4'),
      createMediaItem('sel-test-7', 'video-g.mp4', 'C:/tmp/video-g.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const selectAllButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: /^(全选全部|取消全选)$/ })
    await expect(selectAllButton).toHaveText('全选全部')

    // Click select-all
    await selectAllButton.click()
    await expect(selectAllButton).toHaveText('取消全选')

    // All checkboxes should be checked
    const checkboxes = tauriPage.locator('.media-row input[type="checkbox"]')
    await expect(checkboxes).toHaveCount(3)
    for (let i = 0; i < 3; i++) {
      await expect(checkboxes.nth(i)).toBeChecked()
    }

    // Click again
    await selectAllButton.click()
    await expect(selectAllButton).toHaveText('全选全部')
    for (let i = 0; i < 3; i++) {
      await expect(checkboxes.nth(i)).not.toBeChecked()
    }

    await clearMediaItems(tauriPage)
  })

  test('remove button deletes only the clicked row', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('sel-test-8', 'video-h.mp4', 'C:/tmp/video-h.mp4'),
      createMediaItem('sel-test-9', 'video-i.mp4', 'C:/tmp/video-i.mp4'),
      createMediaItem('sel-test-10', 'video-j.mp4', 'C:/tmp/video-j.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const rows = tauriPage.locator('.media-row')
    await expect(rows).toHaveCount(3)

    // Remove middle row
    const removeButton = rows.nth(1).locator('button.table-action').filter({ hasText: '移除' })
    await removeButton.click()

    await expect(rows).toHaveCount(2)
    await expect(rows.nth(0).locator('.table-primary')).toHaveText('video-h.mp4')
    await expect(rows.nth(1).locator('.table-primary')).toHaveText('video-j.mp4')

    await clearMediaItems(tauriPage)
  })

  test('re-inspect button is disabled when no media exists', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // No media items: re-inspect should be disabled
    const reinspectButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: '重新读取' })
    await expect(reinspectButton).toBeDisabled()

    // Inject media
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('sel-test-11', 'video-k.mp4', 'C:/tmp/video-k.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    await expect(reinspectButton).toBeEnabled()

    await clearMediaItems(tauriPage)
  })

  test('partial selection state persists across rows', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // Inject 3 items with pre-set selection states
    const ok = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return false

      pinia.state.value.media.mediaItems = [
        { id: 'sel-test-12', displayName: 'video-l.mp4', inputPath: 'C:/tmp/video-l.mp4', selected: true, inspecting: false, info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264', audioCodec: 'aac', duration: 60, bitrate: 5000 }, decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} }, encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} }, workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } }, outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 } },
        { id: 'sel-test-13', displayName: 'video-m.mp4', inputPath: 'C:/tmp/video-m.mp4', selected: false, inspecting: false, info: { width: 1280, height: 720, fps: 24, videoCodec: 'hevc', audioCodec: 'aac', duration: 30, bitrate: 3000 }, decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} }, encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} }, workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } }, outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 } },
        { id: 'sel-test-14', displayName: 'video-n.mp4', inputPath: 'C:/tmp/video-n.mp4', selected: true, inspecting: false, info: { width: 3840, height: 2160, fps: 60, videoCodec: 'h264', audioCodec: 'aac', duration: 120, bitrate: 8000 }, decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} }, encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} }, workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, anime: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } }, outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 } },
      ]
      pinia.state.value.media.activeItemId = 'sel-test-12'
      return true
    })
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await expect(tauriPage.locator('.table-wrap')).toBeVisible({ timeout: 5000 })
    const checkboxes = tauriPage.locator('.media-row input[type="checkbox"]')
    await expect(checkboxes).toHaveCount(3)

    // First and third should be checked, second not
    await expect(checkboxes.nth(0)).toBeChecked()
    await expect(checkboxes.nth(1)).not.toBeChecked()
    await expect(checkboxes.nth(2)).toBeChecked()

    // select-all button should show "全选全部" (not all selected)
    const selectAllButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: /^(全选全部|取消全选)$/ })
    await expect(selectAllButton).toHaveText('全选全部')

    await clearMediaItems(tauriPage)
  })
})
