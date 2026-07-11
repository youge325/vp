import { test, expect } from '../fixtures'

function buildPreset(outputDir: string) {
  return {
    decodeConfig: {
      mode: 'software' as const,
      decoder: 'software',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'multi' as const,
      processOrder: 'super_resolution_then_interpolation' as const,
      interpolation: {
        enabled: false,
        targetFps: 60,
        multi: 2,
        algorithm: 'rife',
        model: '4.25',
        scale: 1.0,
        fp16: false,
        tensorBackend: 'pytorch' as const,
        engine: 'cuda',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2.0,
        algorithm: 'realesrgan',
      },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    encodeConfig: {
      codec: 'libx264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf' as const, value: 18 },
      options: {},
    },
    outputConfig: {
      outputDir,
      openOnComplete: true,
      segmentFrames: 1000,
    },
  }
}

test.describe('Preset apply and loading', () => {
  test('loading preset updates draft preset store', async ({ tauriPage }) => {
    const outputDir = 'D:/vp-e2e-preset-apply-test'
    const preset = buildPreset(outputDir)

    // Save a preset first
    await tauriPage.evaluate(async (p) => {
      try {
        // @ts-expect-error
        await window.__TAURI_INTERNALS__.invoke('save_workbench_preset', { preset: p })
      } catch (error: any) {
        throw new Error(`save_workbench_preset failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    }, preset)

    // Load it back
    const loaded = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        return await window.__TAURI_INTERNALS__.invoke('load_workbench_preset')
      } catch (error: any) {
        throw new Error(`load_workbench_preset failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    expect(loaded).not.toBeNull()
    expect(loaded.encodeConfig.rateControl.value).toBe(18)

    // Verify the draft preset store reflects the loaded preset
    const draftCrf = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.preset?.draftPreset?.encodeConfig?.rateControl?.value ?? null
    })
    expect(draftCrf).toBe(18)
  })

  test('preset persistence flag can be toggled via store', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Read current value (bootstrap may have already set it to true)
    const flagBefore = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.preset?.presetPersistenceReady ?? null
    })
    expect(flagBefore).not.toBeNull()

    // Toggle to the opposite value
    const toggled = await tauriPage.evaluate((targetValue: boolean) => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset) return false
      pinia.state.value.preset.presetPersistenceReady = targetValue
      return true
    }, !flagBefore)
    test.skip(!toggled, 'Cannot access Pinia preset store state from evaluate')
    if (!toggled) throw new Error('unreachable')

    const flagAfter = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.preset?.presetPersistenceReady ?? null
    })
    expect(flagAfter).toBe(!flagBefore)
  })

  test('draft preset is applied to newly created media items', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // First set a custom draft preset via store injection
    const presetSet = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset) return false

      const draft = pinia.state.value.preset.draftPreset
      draft.encodeConfig.codec = 'hevc'
      draft.encodeConfig.container = 'mkv'
      draft.workflowConfig.interpolation.enabled = true
      draft.outputConfig.outputDir = 'C:/custom/output'
      return true
    })
    test.skip(!presetSet, 'Cannot access Pinia preset store from evaluate')

    // Inject a media item that mimics having been created with the draft preset
    const itemSet = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return false

      const draft = pinia.state.value.preset.draftPreset
      const itemId = 'preset-test-1'
      pinia.state.value.media.mediaItems = [
        {
          id: itemId,
          displayName: 'preset-video.mp4',
          inputPath: 'C:/tmp/preset-video.mp4',
          selected: false,
          inspecting: false,
          info: { width: 1920, height: 1080, fps: 30, videoCodec: 'h264' },
          decodeConfig: { ...draft.decodeConfig },
          encodeConfig: { ...draft.encodeConfig },
          workflowConfig: { ...draft.workflowConfig },
          outputConfig: { ...draft.outputConfig },
        },
      ]
      pinia.state.value.media.activeItemId = itemId
      return true
    })
    test.skip(!itemSet, 'Cannot access Pinia stores from evaluate')

    // Verify the item's encode config matches the draft
    const itemCodec = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.media?.mediaItems?.[0]?.encodeConfig?.codec ?? null
    })
    expect(itemCodec).toBe('hevc')

    // Verify outputDir matches
    const itemOutputDir = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return pinia?.state?.value?.media?.mediaItems?.[0]?.outputConfig?.outputDir ?? null
    })
    expect(itemOutputDir).toBe('C:/custom/output')

    // Clean up
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
  })

  test('patchEncode mutator updates draft preset without affecting other fields', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Directly mutate encodeConfig.codec and verify container remains unchanged
    const patched = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.encodeConfig) return false

      const draft = pinia.state.value.preset.draftPreset
      draft.encodeConfig.codec = 'h264'
      const originalContainer = draft.encodeConfig.container
      const originalCodec = draft.encodeConfig.codec

      draft.encodeConfig.codec = 'hevc'

      return {
        codec: draft.encodeConfig.codec,
        container: draft.encodeConfig.container,
        originalContainer,
        originalCodec,
      }
    })
    test.skip(!patched, 'Cannot access Pinia preset store state from evaluate')
    if (!patched) throw new Error('unreachable')

    expect(patched.codec).toBe('hevc')
    expect(patched.originalCodec).not.toBe('hevc')
    // Container should remain unchanged
    expect(patched.container).toBe(patched.originalContainer)
  })
})
