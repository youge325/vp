import { test, expect } from '../fixtures'

// Minimal media item shape for injection
interface InjectedMediaItem {
  id: string
  displayName: string
  inputPath: string
  selected: boolean
  inspecting: boolean
  info: {
    width: number
    height: number
    fps: number
    videoCodec: string
  }
  decodeConfig: Record<string, unknown>
  encodeConfig: Record<string, unknown>
  workflowConfig: Record<string, unknown>
  outputConfig: Record<string, unknown>
}

async function injectMediaItems(
  tauriPage: any,
  items: InjectedMediaItem[],
  activeItemId: string | null,
): Promise<boolean> {
  return await tauriPage.evaluate(
    (payload: { items: InjectedMediaItem[]; activeItemId: string | null }) => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return false

      pinia.state.value.media.mediaItems = payload.items
      pinia.state.value.media.activeItemId = payload.activeItemId
      return true
    },
    { items, activeItemId },
  )
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

function makeItem(id: string, displayName: string, selected: boolean): InjectedMediaItem {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
    workflowConfig: {
      fpsMode: 'multi',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: { enabled: false },
      superResolution: { enabled: false },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    outputConfig: { outputDir: 'C:/tmp/output', openOnComplete: false, segmentFrames: 1000 },
  }
}

test.describe('Stage module scope and badge', () => {
  test('preprocess panel badge shows preset label when no active item', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const badge = tauriPage.locator('.panel-badge')
    await expect(badge).toHaveText('默认预设')

    await expect(tauriPage.locator('.panel-copy .panel-caption')).toHaveCount(0)
  })

  test('postprocess panel badge shows file count when active item exists', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("后处理")')
    await expect(tauriPage.locator('h2:has-text("后处理")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [makeItem('scope-1', 'scope-video.mp4', true)], 'scope-1')
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const badge = tauriPage.locator('.panel-badge')
    await expect(badge).toHaveText('作用于 1 个文件')

    await expect(tauriPage.locator('.panel-copy .panel-caption')).toHaveCount(0)

    await clearMediaItems(tauriPage)
  })

  test('filter section appears without pipeline caption when enabled', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    // Default: toggle off, filter section not visible
    const filterSection = tauriPage.locator('.filter-section')
    await expect(filterSection).not.toBeVisible()

    // Enable the stage — the label text is on the outer .field.toggle-field
    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '启用预处理' }).locator('input[type="checkbox"]')
    await toggle.click()

    // Now filter section is visible without explanatory copy
    await expect(filterSection).toBeVisible()
    await expect(filterSection.locator('.panel-caption')).toHaveCount(0)

    // Toggle off again
    await toggle.click()
    await expect(filterSection).not.toBeVisible()
  })

  test('postprocess filter section appears without pipeline caption', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("后处理")')
    await expect(tauriPage.locator('h2:has-text("后处理")')).toBeVisible({ timeout: 5000 })

    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '启用后处理' }).locator('input[type="checkbox"]')
    await toggle.click()

    const filterSection = tauriPage.locator('.filter-section')
    await expect(filterSection).toBeVisible()
    await expect(filterSection.locator('.panel-caption')).toHaveCount(0)
  })

  test('panel badge updates when selection count changes', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const items = [
      makeItem('scope-multi-1', 'video1.mp4', true),
      makeItem('scope-multi-2', 'video2.mp4', true),
      makeItem('scope-multi-3', 'video3.mp4', true),
    ]
    const ok = await injectMediaItems(tauriPage, items, 'scope-multi-1')
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    // Badge shows 3 files (all selected)
    const badge = tauriPage.locator('.panel-badge')
    await expect(badge).toHaveText('作用于 3 个文件')

    // Deselect one item by toggling its checkbox in the store
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.media?.mediaItems) {
          pinia.state.value.media.mediaItems[1].selected = false
        }
      }
    })

    await expect(badge).toHaveText('作用于 2 个文件')

    await clearMediaItems(tauriPage)
  })

  test('FilterChainEditor conditionally rendered via toggle', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("预处理")')
    await expect(tauriPage.locator('h2:has-text("预处理")')).toBeVisible({ timeout: 5000 })

    const toggle = tauriPage.locator('label.field.toggle-field').filter({ hasText: '启用预处理' }).locator('input[type="checkbox"]')

    // Toggle off: no filter section
    await expect(tauriPage.locator('.filter-section')).not.toBeVisible()
    await expect(tauriPage.locator('.filter-empty')).not.toBeVisible()
    await expect(tauriPage.locator('.filter-toolbar')).not.toBeVisible()

    // Toggle on: filter section appears with empty state
    await toggle.click()
    await expect(tauriPage.locator('.filter-section')).toBeVisible()
    await expect(tauriPage.locator('.filter-empty')).toBeVisible()

    // Toggle off again: everything hidden
    await toggle.click()
    await expect(tauriPage.locator('.filter-section')).not.toBeVisible()
  })
})
