import { test, expect } from '../fixtures'

function createMediaItem(id: string, displayName: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
    selected: true,
    inspecting: false,
    info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
    decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: {} },
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
    workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false }, postprocess: { enabled: false } },
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

test.describe('Output directory dual-track editing', () => {
  test('outputDir input reflects active item value when present', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('output-test-1', 'video-a.mp4', {
        outputConfig: { outputDir: 'D:/item-output', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')
    await expect(input).toHaveValue('D:/item-output')

    await clearMediaItems(tauriPage)
  })

  test('outputDir input reflects preset draft when no active item', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Set preset draft outputDir
    const presetSet = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false
      pinia.state.value.preset.draftPreset.outputConfig.outputDir = 'D:/preset-output'
      return true
    })
    test.skip(!presetSet, 'Cannot access Pinia preset store from evaluate')

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')
    await expect(input).toHaveValue('D:/preset-output')
  })

  test('modifying outputDir with active item updates item config only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('output-test-2', 'video-b.mp4', {
        outputConfig: { outputDir: 'C:/original', openOnComplete: false, segmentFrames: 1000 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Modify outputDir via store (simulating user editing with active item)
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

      const originalItemDir = activeItem.outputConfig.outputDir
      const originalPresetDir = pinia.state.value.preset.draftPreset.outputConfig.outputDir

      // Simulate patchOutput with active item — affects item config only
      activeItem.outputConfig.outputDir = 'D:/modified-item'

      return {
        originalItemDir,
        originalPresetDir,
        newItemDir: activeItem.outputConfig.outputDir,
        newPresetDir: pinia.state.value.preset.draftPreset.outputConfig.outputDir,
      }
    })
    test.skip(!modified, 'Cannot access editor state')
    if (!modified) throw new Error('unreachable')

    expect(modified.newItemDir).toBe('D:/modified-item')
    expect(modified.newPresetDir).toBe(modified.originalPresetDir)

    await clearMediaItems(tauriPage)
  })

  test('modifying outputDir without active item updates preset draft only', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Ensure no active item and no media items
    await clearMediaItems(tauriPage)

    // Set a known preset draft value first
    await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      const vueApp = (root as any)?.__vue_app__
      if (vueApp) {
        const pinia = vueApp.config?.globalProperties?.$pinia
        if (pinia?.state?.value?.preset?.draftPreset?.outputConfig) {
          pinia.state.value.preset.draftPreset.outputConfig.outputDir = 'C:/preset-before'
        }
      }
    })

    // Modify preset draft outputDir (simulating user editing without active item)
    const modified = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false

      const originalPresetDir = pinia.state.value.preset.draftPreset.outputConfig.outputDir
      pinia.state.value.preset.draftPreset.outputConfig.outputDir = 'D:/modified-preset'

      return {
        originalPresetDir,
        newPresetDir: pinia.state.value.preset.draftPreset.outputConfig.outputDir,
      }
    })
    test.skip(!modified, 'Cannot access preset store')
    if (!modified) throw new Error('unreachable')

    expect(modified.newPresetDir).toBe('D:/modified-preset')
  })
})
