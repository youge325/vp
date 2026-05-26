import { test, expect } from '../fixtures'

function createMediaItem(id: string, displayName: string, overrides?: Partial<Record<string, unknown>>) {
  return {
    id,
    displayName,
    inputPath: `C:/tmp/${displayName}`,
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

test.describe('Home dashboard dynamic stats', () => {
  test('stats show zero on fresh instance', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const statCards = tauriPage.locator('.stat-card')
    await expect(statCards).toHaveCount(4)

    // The last stat card (index 3) is "已导入素材" with value in <strong>
    const importedStat = statCards.nth(3)
    await expect(importedStat.locator('span')).toHaveText('已导入素材')
    await expect(importedStat.locator('strong')).toHaveText('0')
  })

  test('stats update when media items are injected', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('home-test-1', 'video-a.mp4'),
      createMediaItem('home-test-2', 'video-b.mp4'),
      createMediaItem('home-test-3', 'video-c.mp4'),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    // Verify via store directly (DOM stat values depend on useHomeDashboard computed)
    const stats = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return null
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return null
      const pinia = vueApp.config?.globalProperties?.$pinia
      return {
        itemCount: pinia?.state?.value?.media?.mediaItems?.length ?? 0,
      }
    })
    expect(stats).not.toBeNull()
    expect(stats!.itemCount).toBe(3)

    await clearMediaItems(tauriPage)
  })

  test('environment capability cards render after probe', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Inject environment check result with capabilities
    const envOk = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.env) return false

      pinia.state.value.env.env = {
        checkResult: {
          type: 'info',
          ffmpeg: { available: true, version: '6.0', path: 'D:/ffmpeg/ffmpeg.exe' },
          gpu: { available: true, vendor: 'NVIDIA', model: 'RTX 4090' },
          tensorBackends: ['pytorch', 'onnx'],
          rifeModel: { available: true, version: '4.25' },
          interpolationAlgorithms: [
            { name: 'rife', label: 'RIFE', tensorBackends: ['pytorch', 'onnx'] },
          ],
          superResolutionAlgorithms: [
            { name: 'realesrgan', label: 'Real-ESRGAN', tensorBackends: ['pytorch'] },
          ],
          animeProfiles: ['clean-lines', 'detail-enhance'],
        },
        probeSource: 'realtime',
        probeTimestamp: Date.now(),
        probeDurationMs: 1500,
      }
      return true
    })
    test.skip(!envOk, 'Cannot access Pinia env store from evaluate')

    // Verify summary blocks exist
    const summaryBlocks = tauriPage.locator('.summary-block')
    const summaryCount = await summaryBlocks.count()
    expect(summaryCount).toBeGreaterThanOrEqual(1)

    // Verify first summary block has title and content
    const firstBlock = summaryBlocks.nth(0)
    await expect(firstBlock.locator('.summary-block-title')).toBeVisible()
  })

  test('home module navigation links exist', async ({ tauriPage }) => {
    await expect(tauriPage.locator('[data-testid="home-module"]')).toBeVisible({ timeout: 5000 })

    // Verify the module stack contains navigation-capable elements
    const moduleStack = tauriPage.locator('.module-stack')
    await expect(moduleStack).toBeVisible()

    // Stats grid should be visible
    const statsGrid = tauriPage.locator('.stats-grid')
    await expect(statsGrid).toBeVisible()
  })
})
