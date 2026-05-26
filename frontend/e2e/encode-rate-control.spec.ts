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
    encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf' as const, value: 23 }, options: {} },
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

test.describe('Encode module rate control', () => {
  test('rate control mode select has three options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const modeSelect = tauriPage.locator('label.field').filter({ hasText: '码率控制模式' }).locator('select')
    await expect(modeSelect).toBeVisible()

    const options = await modeSelect.locator('option').allTextContents()
    expect(options).toContain('CRF')
    expect(options).toContain('QP')
    expect(options).toContain('Bitrate')
  })

  test('switching mode updates the selected value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const modeSelect = tauriPage.locator('label.field').filter({ hasText: '码率控制模式' }).locator('select')
    await expect(modeSelect).toBeVisible()

    // Switch to QP
    await modeSelect.selectOption({ label: 'QP' })
    const qpValue = await modeSelect.inputValue()
    expect(qpValue).toBeTruthy()

    // Switch to Bitrate
    await modeSelect.selectOption({ label: 'Bitrate' })
    const bitrateValue = await modeSelect.inputValue()
    expect(bitrateValue).toBeTruthy()
    expect(bitrateValue).not.toBe(qpValue)

    // Switch back to CRF
    await modeSelect.selectOption({ label: 'CRF' })
    const crfValue = await modeSelect.inputValue()
    expect(crfValue).toBeTruthy()
  })

  test('rate control value input accepts new values', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const valueInput = tauriPage.locator('label.field').filter({ hasText: '码率控制值' }).locator('input')
    await expect(valueInput).toBeVisible()

    await valueInput.fill('28')
    await valueInput.blur()
    await expect(valueInput).toHaveValue('28')
  })

  test('rate control value persists after mode switch', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const modeSelect = tauriPage.locator('label.field').filter({ hasText: '码率控制模式' }).locator('select')
    const valueInput = tauriPage.locator('label.field').filter({ hasText: '码率控制值' }).locator('input')

    await expect(modeSelect).toBeVisible()
    await expect(valueInput).toBeVisible()

    // Set a custom value
    await valueInput.fill('18')
    await valueInput.blur()
    await expect(valueInput).toHaveValue('18')

    // Switch mode
    await modeSelect.selectOption({ label: 'QP' })

    // Switch back to CRF
    await modeSelect.selectOption({ label: 'CRF' })

    // Value should still be 18 (stored in preset/individual item config)
    await expect(valueInput).toHaveValue('18')
  })

  test('rate control value reflects active item config', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("输入")')
    await expect(tauriPage.locator('h2:has-text("批量导入")')).toBeVisible({ timeout: 5000 })

    const ok = await injectMediaItems(tauriPage, [
      createMediaItem('rate-test-1', 'video-a.mp4', {
        encodeConfig: { codec: 'h264', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf' as const, value: 15 }, options: {} },
      }),
    ])
    test.skip(!ok, 'Cannot access Pinia media store from evaluate')

    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const valueInput = tauriPage.locator('label.field').filter({ hasText: '码率控制值' }).locator('input')
    await expect(valueInput).toHaveValue('15')

    await clearMediaItems(tauriPage)
  })
})
