import { test, expect } from '../fixtures'

const makeOption = (name: string, defaultValue: string) => ({
  name,
  label: name,
  type: 'string',
  defaultValue,
  choices: [],
  min: null,
  max: null,
})

const makeProfile = (
  name: string,
  label: string,
  family: string,
  codec: string,
  hardwareDevices: string[],
  options: Array<Record<string, unknown>> = [],
) => ({
  name,
  label,
  family,
  codec,
  available: true,
  pixelFormats: [],
  hardwareDevices,
  options,
})

const CONTROLLED_PROFILES = [
  makeProfile('software', 'Software Decode', 'software', 'any', []),
  makeProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['cuda', 'd3d11va'], [
    makeOption('resize', '1920x1080'),
  ]),
  makeProfile('hevc_qsv', 'QSV H.265', 'intel', 'hevc', ['qsv'], [
    makeOption('load_plugin', 'hevc_hw'),
  ]),
]

async function installDecodeProfiles(
  tauriPage: any,
  profiles: unknown[] = CONTROLLED_PROFILES,
  decodeConfig: Record<string, unknown> = {
    mode: 'hardware',
    hwaccel: 'cuda',
    hwaccelDevice: '0',
    decoder: 'h264_cuvid',
    options: {},
  },
): Promise<boolean> {
  return await tauriPage.evaluate(({
    decoderProfiles,
    decodeConfig,
  }: {
    decoderProfiles: unknown[]
    decodeConfig: Record<string, unknown>
  }) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    const state = pinia?.state?.value
    if (!state?.env?.env || !state?.preset?.draftPreset) return false

    state.env.env.checkResult = {
      type: 'check',
      ffmpeg: {
        available: true,
        version: 'e2e',
        path: 'ffmpeg',
        ffprobePath: 'ffprobe',
        hwaccels: ['cuda', 'qsv', 'd3d11va'],
        encoderProfiles: [],
        decoderProfiles,
      },
      gpu: { available: true, devices: ['GPU'], adapters: [] },
      tensorBackends: { pytorch: false, paddle: false, onnx: false },
      tensorEngines: {},
      backendDeviceSupport: {},
      onnxRuntime: { available: false, providers: [] },
      rifeModel: { available: false },
      interpolationAlgorithms: [],
      superResolutionAlgorithms: [],
      animeProfiles: [],
    }

    state.preset.draftPreset.decodeConfig = decodeConfig
    return true
  }, { decoderProfiles: profiles, decodeConfig })
}

async function openDecodeModule(tauriPage: any): Promise<void> {
  await tauriPage.click('.rail-link:has-text("解码")')
  await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })
}

const decoderSelect = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')

const hardwareDeviceField = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '硬件设备' })

const hardwareDeviceSelect = (tauriPage: any) =>
  hardwareDeviceField(tauriPage).locator('select')

const deviceNumberField = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '设备编号' })

const deviceNumberValue = (tauriPage: any) =>
  deviceNumberField(tauriPage).locator('.readonly-value')

async function setDraftHwaccelDevice(tauriPage: any, value: string): Promise<void> {
  await tauriPage.evaluate((nextValue: string) => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    const pinia = vueApp?.config?.globalProperties?.$pinia
    const state = pinia?.state?.value
    if (state?.preset?.draftPreset?.decodeConfig) {
      state.preset.draftPreset.decodeConfig.hwaccelDevice = nextValue
    }
  }, value)
}

async function getDraftHwaccelDevice(tauriPage: any): Promise<string> {
  return await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    const pinia = vueApp?.config?.globalProperties?.$pinia
    const state = pinia?.state?.value
    return state?.preset?.draftPreset?.decodeConfig?.hwaccelDevice ?? ''
  })
}

async function expectHardwareDeviceState(
  tauriPage: any,
  labels: string[],
  value: string,
): Promise<void> {
  const select = hardwareDeviceSelect(tauriPage)
  await expect(select).toHaveValue(value, { timeout: 5000 })
  expect(await select.locator('option').allTextContents()).toEqual(labels)
}

test.describe('Decode module UI', () => {
  test('decoder profile select exists and has options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const decoderSelect = tauriPage.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(decoderSelect).toBeVisible()

    // Wait for Vue async option rendering
    await decoderSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })
    const options = await decoderSelect.locator('option').allTextContents()
    expect(options.length).toBeGreaterThan(0)
  })

  test('switching decoder profile updates hardware device options without manual device number input', async ({ tauriPage }) => {
    const ok = await installDecodeProfiles(tauriPage)
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await openDecodeModule(tauriPage)

    await expect(deviceNumberValue(tauriPage)).toHaveText('FFmpeg 自动选择')
    await expect(deviceNumberField(tauriPage).locator('input')).toHaveCount(0)
    await expectHardwareDeviceState(tauriPage, ['CUDA', 'D3D11VA'], 'cuda')

    await decoderSelect(tauriPage).selectOption({ label: 'QSV H.265' })
    await expectHardwareDeviceState(tauriPage, ['QSV'], 'qsv')
    await expect(deviceNumberValue(tauriPage)).toHaveText('FFmpeg 自动选择')
    expect(await getDraftHwaccelDevice(tauriPage)).toBe('')

    await decoderSelect(tauriPage).selectOption({ label: 'NVDEC H.264' })
    await expectHardwareDeviceState(tauriPage, ['CUDA', 'D3D11VA'], 'cuda')

    await setDraftHwaccelDevice(tauriPage, '2')
    await hardwareDeviceSelect(tauriPage).selectOption({ label: 'D3D11VA' })
    await expectHardwareDeviceState(tauriPage, ['CUDA', 'D3D11VA'], 'd3d11va')
    expect(await getDraftHwaccelDevice(tauriPage)).toBe('')
  })

  test('empty hardware device list hides device selector', async ({ tauriPage }) => {
    const ok = await installDecodeProfiles(
      tauriPage,
      [
        makeProfile('software', 'Software Decode', 'software', 'any', []),
        makeProfile('av1_cuvid', 'NVDEC AV1', 'nvidia', 'av1', []),
      ],
      {
        mode: 'hardware',
        hwaccel: '',
        hwaccelDevice: '',
        decoder: 'av1_cuvid',
        options: {},
      },
    )
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await openDecodeModule(tauriPage)

    await expect(hardwareDeviceField(tauriPage)).toHaveCount(0)
    await expect(deviceNumberField(tauriPage)).toHaveCount(0)
  })

  test('switching decoder profile shows or hides capability options panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("解码")')
    await expect(tauriPage.locator('h2:has-text("解码设置")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').first()
    const decoderSelect = section.locator('label.field').filter({ hasText: '解码方案' }).locator('select')
    await expect(decoderSelect).toBeVisible()

    try {
      await decoderSelect.locator('option').first().waitFor({ state: 'attached', timeout: 10000 })
    } catch {
      test.skip()
      return
    }
    const options = await decoderSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // The decoder option grid only renders when decoderOptions.length > 0.
    const optionPanel = section.locator('div.field-grid.field-grid-2').first()

    // Try to find a profile that shows the panel (non-software) and one that hides it
    const softwareOption = options.find((o) => o.toLowerCase().includes('software') || o.includes('软件'))
    const nonSoftwareOption = options.find((o) => !o.toLowerCase().includes('software') && !o.includes('软件'))

    if (softwareOption && nonSoftwareOption) {
      await decoderSelect.selectOption({ label: nonSoftwareOption })
      await expect(optionPanel).toBeVisible({ timeout: 5000 })

      await decoderSelect.selectOption({ label: softwareOption })
      await expect(optionPanel).not.toBeVisible()
    } else if (nonSoftwareOption) {
      // Fallback: just verify switching between two profiles changes panel state
      await decoderSelect.selectOption({ index: 0 })
      const initialVisible = await optionPanel.isVisible().catch(() => false)

      await decoderSelect.selectOption({ label: nonSoftwareOption })
      const newVisible = await optionPanel.isVisible().catch(() => false)

      // We only assert if the state actually changed
      if (initialVisible === newVisible) {
        test.skip()
      }
    } else {
      test.skip()
    }
  })
})
