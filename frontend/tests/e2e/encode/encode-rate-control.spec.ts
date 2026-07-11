import { test, expect } from '../fixtures'

const makeNumberOption = (name: string, defaultValue: number) => ({
  name,
  label: name,
  type: 'number',
  defaultValue,
  choices: [],
  min: 0,
  max: 51,
})

const makeProfile = (
  name: string,
  label: string,
  family: string,
  rateControlModes: Array<{ mode: string; label: string; defaultValue: number; unit: string }>,
  options: Array<Record<string, unknown>>,
) => ({
  name,
  label,
  family,
  codec: 'h264',
  available: true,
  hardwareDevices: [],
  options,
  rateControlModes,
})

const CONTROLLED_PROFILES = [
  makeProfile(
    'libx264',
    'CPU H.264',
    'cpu',
    [
      { mode: 'crf', label: 'CRF', defaultValue: 19, unit: 'CRF' },
      { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
    ],
    [makeNumberOption('crf', 19)],
  ),
  makeProfile(
    'h264_nvenc',
    'NVENC H.264',
    'nvidia',
    [
      { mode: 'cq', label: 'CQ', defaultValue: 21, unit: 'CQ' },
      { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
    ],
    [makeNumberOption('cq', 21)],
  ),
  makeProfile(
    'h264_qsv',
    'QSV H.264',
    'intel',
    [
      { mode: 'qp', label: 'QP', defaultValue: 25, unit: 'QP' },
      { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
    ],
    [makeNumberOption('qp', 25)],
  ),
]

async function installEncodeProfiles(
  tauriPage: any,
  profiles: unknown[] = CONTROLLED_PROFILES,
): Promise<boolean> {
  return await tauriPage.evaluate((encoderProfiles: unknown[]) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    const state = pinia?.state?.value
    if (!state?.env?.env || !state?.preset?.draftPreset) return false

    state.env.env.checkResult = {
      ffmpeg: {
        available: true,
        hwaccels: [],
        encoderProfiles,
        decoderProfiles: [],
      },
      gpu: { adapters: [] },
      tensorEngines: { pytorch: [], paddle: [], onnx: [] },
      backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
      interpolationAlgorithms: [],
      superResolutionAlgorithms: [],
      runtimeMode: 'e2e',
    }

    state.preset.draftPreset.encodeConfig = {
      codec: 'libx264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf', value: 19 },
      options: {},
    }
    state.preset.draftPreset.outputConfig = {
      outputDir: 'C:/tmp/output',
      openOnComplete: false,
      segmentFrames: 1000,
    }
    return true
  }, profiles)
}

async function openEncodeModule(tauriPage: any): Promise<void> {
  await tauriPage.click('.rail-link:has-text("编码")')
  await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })
}

const encoderSelect = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '编码器' }).locator('select')

const modeField = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '码率控制模式' })

const valueField = (tauriPage: any) =>
  tauriPage.locator('label.field').filter({ hasText: '码率控制值' })

async function expectRateControlState(
  tauriPage: any,
  labels: string[],
  mode: string,
  value: string,
  unit: string,
): Promise<void> {
  const modeSelect = modeField(tauriPage).locator('select')
  const valueInput = valueField(tauriPage).locator('input')

  await expect(modeSelect).toHaveValue(mode, { timeout: 5000 })
  await expect(valueInput).toHaveValue(value, { timeout: 5000 })
  await expect(valueField(tauriPage).locator('.field-hint')).toHaveText(`单位: ${unit}`, { timeout: 5000 })
  expect(await modeSelect.locator('option').allTextContents()).toEqual(labels)
}

test.describe('Encode module rate control', () => {
  test('switching encoder updates supported mode, value and unit', async ({ tauriPage }) => {
    const ok = await installEncodeProfiles(tauriPage)
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await openEncodeModule(tauriPage)

    const codecSelect = encoderSelect(tauriPage)
    await expect(codecSelect).toBeVisible({ timeout: 5000 })

    await expectRateControlState(tauriPage, ['CRF', 'Bitrate'], 'crf', '19', 'CRF')

    await codecSelect.selectOption({ label: 'NVENC H.264' })
    await expectRateControlState(tauriPage, ['CQ', 'Bitrate'], 'cq', '21', 'CQ')

    await codecSelect.selectOption({ label: 'QSV H.264' })
    await expectRateControlState(tauriPage, ['QP', 'Bitrate'], 'qp', '25', 'QP')
  })

  test('switching rate control mode updates value and unit', async ({ tauriPage }) => {
    const ok = await installEncodeProfiles(tauriPage)
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await openEncodeModule(tauriPage)

    const modeSelect = modeField(tauriPage).locator('select')
    await expect(modeSelect).toBeVisible({ timeout: 5000 })

    await modeSelect.selectOption({ label: 'Bitrate' })
    await expectRateControlState(tauriPage, ['CRF', 'Bitrate'], 'bitrate', '8', 'Mbps')

    await modeSelect.selectOption({ label: 'CRF' })
    await expectRateControlState(tauriPage, ['CRF', 'Bitrate'], 'crf', '19', 'CRF')
  })

  test('empty rateControlModes disables mode and value controls', async ({ tauriPage }) => {
    const ok = await installEncodeProfiles(tauriPage, [
      makeProfile('libx264', 'CPU H.264', 'cpu', [], [makeNumberOption('crf', 19)]),
    ])
    test.skip(!ok, 'Cannot access Pinia stores from evaluate')

    await openEncodeModule(tauriPage)

    const modeSelect = modeField(tauriPage).locator('select')
    const valueInput = valueField(tauriPage).locator('input')

    await expect(modeSelect).toBeDisabled({ timeout: 5000 })
    await expect(valueInput).toBeDisabled({ timeout: 5000 })
    await expect(modeField(tauriPage).locator('.field-hint')).toHaveText(
      '未探测到可用码率控制模式',
      { timeout: 5000 },
    )
  })
})
