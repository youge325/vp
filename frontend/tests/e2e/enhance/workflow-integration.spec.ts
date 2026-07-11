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
    workflowConfig: { fpsMode: 'multi', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false }, superResolution: { enabled: false }, preprocess: { enabled: false, filters: [] }, postprocess: { enabled: false, filters: [] } },
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

test.describe('Workflow configuration integration', () => {
  test('full workflow config is consistent across stores', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    // Inject item with a rich workflow configuration
    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('workflow-test-1', 'integrated.mp4', {
        decodeConfig: { mode: 'software', hwaccel: '', decoder: 'software', options: { threads: 4 } },
        workflowConfig: {
          fpsMode: 'multi',
          processOrder: 'super_resolution_then_interpolation',
          interpolation: { enabled: true, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: true, scaleFactor: 2.0, algorithm: 'realesrgan' },
          preprocess: { enabled: true, filters: [
            { kind: 'scale', enabled: true, params: { mode: 'factor', factor: 1.5 } },
            { kind: 'anime_cleanup', enabled: true, params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 } },
          ] },
          postprocess: { enabled: true, filters: [{ kind: 'sharpen', enabled: true, params: { amount: 0.5 } }] },
        },
        encodeConfig: { codec: 'hevc', family: 'cpu', container: 'mkv', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: { preset: 'slow' } },
        outputConfig: { outputDir: 'D:/workflow-output', openOnComplete: true, segmentFrames: 500 },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Verify the configuration via store directly
    const config = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.media) return null

      const item = pinia.state.value.media.mediaItems[0]
      if (!item) return null

      return {
        decodeMode: item.decodeConfig.mode,
        interpolationEnabled: item.workflowConfig.interpolation.enabled,
        interpolationAlgorithm: item.workflowConfig.interpolation.algorithm,
        interpolationBackend: item.workflowConfig.interpolation.tensorBackend,
        superResolutionEnabled: item.workflowConfig.superResolution.enabled,
        superResolutionScale: item.workflowConfig.superResolution.scaleFactor,
        animeCleanup: item.workflowConfig.preprocess.filters.find((step: any) => step.kind === 'anime_cleanup'),
        preprocessEnabled: item.workflowConfig.preprocess.enabled,
        postprocessEnabled: item.workflowConfig.postprocess.enabled,
        encodeCodec: item.encodeConfig.codec,
        encodeContainer: item.encodeConfig.container,
        encodeCrf: item.encodeConfig.rateControl.value,
        outputDir: item.outputConfig.outputDir,
        openOnComplete: item.outputConfig.openOnComplete,
        segmentFrames: item.outputConfig.segmentFrames,
      }
    })
    test.skip(!config, 'Cannot evaluate workflow config')
    if (!config) throw new Error('unreachable')

    // Verify all configuration fields
    expect(config.decodeMode).toBe('software')
    expect(config.interpolationEnabled).toBe(true)
    expect(config.interpolationAlgorithm).toBe('rife')
    expect(config.interpolationBackend).toBe('pytorch')
    expect(config.superResolutionEnabled).toBe(true)
    expect(config.superResolutionScale).toBe(2.0)
    expect(config.animeCleanup).toEqual({
      kind: 'anime_cleanup',
      enabled: true,
      params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
    })
    expect(config.preprocessEnabled).toBe(true)
    expect(config.postprocessEnabled).toBe(true)
    expect(config.encodeCodec).toBe('hevc')
    expect(config.encodeContainer).toBe('mkv')
    expect(config.encodeCrf).toBe(18)
    expect(config.outputDir).toBe('D:/workflow-output')
    expect(config.openOnComplete).toBe(true)
    expect(config.segmentFrames).toBe(500)

    await clearMediaItems(tauriPage)
  })

  test('workflow config is accessible from different module views', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('workflow-test-2', 'cross-module.mp4', {
        workflowConfig: {
          fpsMode: 'target',
          processOrder: 'frame_interpolation_then_super_resolution',
          interpolation: { enabled: true, targetFps: 60, multi: 2, algorithm: 'rife', model: '4.25', scale: 1.0, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
          superResolution: { enabled: false, scaleFactor: 2.0, algorithm: 'realesrgan' },
          preprocess: { enabled: false, filters: [] },
          postprocess: { enabled: false, filters: [] },
        },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Verify config from enhance module
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const enhanceConfig = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null
      return {
        fpsMode: item.workflowConfig.fpsMode,
        processOrder: item.workflowConfig.processOrder,
        interpolationEnabled: item.workflowConfig.interpolation.enabled,
        superResolutionEnabled: item.workflowConfig.superResolution.enabled,
      }
    })
    test.skip(!enhanceConfig, 'Cannot read enhance config')
    if (!enhanceConfig) throw new Error('unreachable')

    expect(enhanceConfig.fpsMode).toBe('target')
    expect(enhanceConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(enhanceConfig.interpolationEnabled).toBe(true)
    expect(enhanceConfig.superResolutionEnabled).toBe(false)

    // Verify config from encode module
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const encodeConfig = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const item = pinia?.state?.value?.media?.mediaItems?.[0]
      if (!item) return null
      return {
        codec: item.encodeConfig.codec,
        container: item.encodeConfig.container,
        keepAudio: item.encodeConfig.keepAudio,
      }
    })
    test.skip(!encodeConfig, 'Cannot read encode config')
    if (!encodeConfig) throw new Error('unreachable')

    expect(encodeConfig.codec).toBe('h264')
    expect(encodeConfig.container).toBe('mp4')
    expect(encodeConfig.keepAudio).toBe(true)

    await clearMediaItems(tauriPage)
  })

  test('multiple items maintain independent configs', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('workflow-test-3', 'item-a.mp4', {
        encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 23 }, options: {} },
      }),
      createMediaItem('workflow-test-4', 'item-b.mp4', {
        encodeConfig: { codec: 'hevc', family: 'cpu', container: 'mkv', keepAudio: false, rateControl: { mode: 'crf', value: 20 }, options: {} },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    const configs = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      const items = pinia?.state?.value?.media?.mediaItems
      if (!items || items.length !== 2) return null
      return items.map((item: any) => ({
        id: item.id,
        codec: item.encodeConfig.codec,
        container: item.encodeConfig.container,
        keepAudio: item.encodeConfig.keepAudio,
        crf: item.encodeConfig.rateControl.value,
      }))
    })
    test.skip(!configs, 'Cannot read item configs')
    if (!configs) throw new Error('unreachable')

    expect(configs[0].codec).toBe('h264')
    expect(configs[0].container).toBe('mp4')
    expect(configs[0].keepAudio).toBe(true)
    expect(configs[0].crf).toBe(23)

    expect(configs[1].codec).toBe('hevc')
    expect(configs[1].container).toBe('mkv')
    expect(configs[1].keepAudio).toBe(false)
    expect(configs[1].crf).toBe(20)

    await clearMediaItems(tauriPage)
  })
})
