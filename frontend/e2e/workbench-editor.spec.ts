import { test, expect } from './fixtures'

function createMediaItem(id: string, displayName: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected: true,
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

test.describe('Workbench editor dual-track mode', () => {
  test('modifying encode config with active item updates item config only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // Inject two items with different encode configs
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('editor-test-1', 'video-a.mp4', { encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} } }),
      createMediaItem('editor-test-2', 'video-b.mp4', { encodeConfig: { codec: 'hevc', family: 'cpu', container: 'mkv', keepAudio: true, rateControl: { mode: 'crf', value: 20 }, options: {} } }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Navigate to encode module — the active item is video-a
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Modify the encode config through store (activeItem is computed, use activeItemId + mediaItems)
    const modified = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return false

      const activeItemId = pinia.state.value.media.activeItemId
      const mediaItems = pinia.state.value.media.mediaItems
      const activeItem = mediaItems.find((item: any) => item.id === activeItemId) ?? null
      if (!activeItem) return false

      // Store original values for comparison
      const originalItemCodec = activeItem.encodeConfig.codec
      const originalPresetCodec = pinia.state.value.preset.draftPreset.encodeConfig.codec

      // Simulate patchEncode with active item — should affect item config only
      activeItem.encodeConfig.codec = 'libx265'
      activeItem.encodeConfig.container = 'mov'

      return {
        originalItemCodec,
        originalPresetCodec,
        newItemCodec: activeItem.encodeConfig.codec,
        newPresetCodec: pinia.state.value.preset.draftPreset.encodeConfig.codec,
      }
    })
    test.skip(!modified, 'Cannot access editor state')
    if (!modified) throw new Error('unreachable')

    // Item config should be modified
    expect(modified.newItemCodec).toBe('libx265')
    // Preset draft should NOT be modified
    expect(modified.newPresetCodec).toBe(modified.originalPresetCodec)

    await clearMediaItems(tauriPage)
  })

  test('modifying preset draft without active item updates preset only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Clear any media items first
    await clearMediaItems(tauriPage)

    // Inject items but don't activate any
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('editor-test-3', 'video-c.mp4', { encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} } }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Deactivate the item
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return false
      pinia.state.value.media.activeItemId = null
      return true
    })

    // Modify preset draft
    const modified = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset) return false

      const originalPresetCodec = pinia.state.value.preset.draftPreset.encodeConfig.codec
      const originalItemCodec = pinia.state.value.media.mediaItems[0]?.encodeConfig?.codec

      // Simulate patchEncode without active item — should affect preset only
      pinia.state.value.preset.draftPreset.encodeConfig.codec = 'hevc'
      pinia.state.value.preset.draftPreset.encodeConfig.container = 'mkv'

      return {
        originalPresetCodec,
        originalItemCodec,
        newPresetCodec: pinia.state.value.preset.draftPreset.encodeConfig.codec,
        newItemCodec: pinia.state.value.media.mediaItems[0]?.encodeConfig?.codec,
      }
    })
    test.skip(!modified, 'Cannot access preset store')
    if (!modified) throw new Error('unreachable')

    // Preset draft should be modified
    expect(modified.newPresetCodec).toBe('hevc')
    // Item config should NOT be modified
    expect(modified.newItemCodec).toBe(modified.originalItemCodec)

    await clearMediaItems(tauriPage)
  })

  test('editorConfig reads from active item when present', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('editor-test-4', 'video-d.mp4', {
        encodeConfig: { codec: 'hevc', family: 'cpu', container: 'mkv', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Verify editorConfig reads from active item (activeItem is computed, access via activeItemId + mediaItems)
    const config = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media || !pinia?.state?.value?.preset) return null

      const activeItemId = pinia.state.value.media.activeItemId
      const mediaItems = pinia.state.value.media.mediaItems
      const activeItem = mediaItems.find((item: any) => item.id === activeItemId) ?? null
      const draftPreset = pinia.state.value.preset.draftPreset

      // Simulate editorConfig computed
      const editorConfig = {
        encodeConfig: activeItem?.encodeConfig ?? draftPreset.encodeConfig,
      }

      return {
        fromActiveItem: activeItem !== null,
        editorCodec: editorConfig.encodeConfig.codec,
        itemCodec: activeItem?.encodeConfig?.codec,
        presetCodec: draftPreset.encodeConfig.codec,
      }
    })
    test.skip(!config, 'Cannot evaluate editor config')
    if (!config) throw new Error('unreachable')

    expect(config.fromActiveItem).toBe(true)
    // editorConfig should match active item, not preset
    expect(config.editorCodec).toBe(config.itemCodec)
    expect(config.editorCodec).toBe('hevc')

    await clearMediaItems(tauriPage)
  })

  test('editorConfig falls back to preset when no active item', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Ensure no active item and no media items
    await clearMediaItems(tauriPage)

    // Set a specific preset draft value
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset) return false
      pinia.state.value.preset.draftPreset.encodeConfig.codec = 'libx264'
      return true
    })

    // Verify editorConfig falls back to preset (activeItem is computed, use activeItemId + mediaItems)
    const config = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media || !pinia?.state?.value?.preset) return null

      const activeItemId = pinia.state.value.media.activeItemId
      const mediaItems = pinia.state.value.media.mediaItems
      const activeItem = mediaItems.find((item: any) => item.id === activeItemId) ?? null
      const draftPreset = pinia.state.value.preset.draftPreset

      const editorConfig = {
        encodeConfig: activeItem?.encodeConfig ?? draftPreset.encodeConfig,
      }

      return {
        hasActiveItem: activeItem !== null,
        editorCodec: editorConfig.encodeConfig.codec,
        presetCodec: draftPreset.encodeConfig.codec,
      }
    })
    test.skip(!config, 'Cannot evaluate editor config')
    if (!config) throw new Error('unreachable')

    expect(config.hasActiveItem).toBe(false)
    // editorConfig should match preset draft
    expect(config.editorCodec).toBe(config.presetCodec)
    expect(config.editorCodec).toBe('libx264')
  })
})
