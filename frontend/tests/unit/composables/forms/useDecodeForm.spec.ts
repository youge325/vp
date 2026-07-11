import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useDecodeForm } from '@/composables/forms/useDecodeForm'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { HardwareDeviceOptionSpec } from '@/types/domain/capability'

const stringOption = (name: string, defaultValue: string) => ({
  name,
  label: name,
  type: 'string' as const,
  defaultValue,
  choices: [],
  min: null,
  max: null,
})

const decoderProfile = (
  name: string,
  label: string,
  family: 'software' | 'nvidia' | 'intel',
  codec: string,
  hardwareDevices: string[],
  hardwareDeviceOptions: Record<string, HardwareDeviceOptionSpec[]> = {},
  options = [stringOption('resize', '1920x1080')],
) => ({
  name,
  label,
  family,
  codec,
  available: true,
  hardwareDevices,
  hardwareDeviceOptions,
  options,
})

const makeEnv = (): EnvironmentCheckResult => ({
  ffmpeg: {
    available: true,
    hwaccels: ['cuda', 'qsv', 'd3d11va'],
    encoderProfiles: [],
    decoderProfiles: [
      decoderProfile('software', 'Software Decode', 'software', 'any', [], {}, []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['cuda', 'd3d11va'], {
        cuda: [
          { value: '0', label: '0' },
          { value: '1', label: '1' },
        ],
        d3d11va: [{ value: 'd3d11-0', label: 'D3D11 0' }],
      }),
      decoderProfile('hevc_qsv', 'QSV H.265', 'intel', 'hevc', ['qsv'], {
        qsv: [{ value: 'qsv0', label: 'QSV 0' }],
      }, [stringOption('load_plugin', 'hevc_hw')]),
      decoderProfile('av1_cuvid', 'NVDEC AV1', 'nvidia', 'av1', []),
    ],
  },
  gpu: { adapters: [] },
  tensorEngines: { pytorch: [], paddle: [], onnx: [] },
  backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  runtimeMode: 'external',
})

describe('useDecodeForm decoder hardware devices', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-06-21T00:00:00Z',
    )
  })

  it('switches decoder profile to the first verified hardware device and probed device number', () => {
    const presetStore = usePresetStore()
    presetStore.patchDecode((config) => {
      config.mode = 'hardware'
      config.hwaccel = 'cuda'
      config.hwaccelDevice = '0'
      config.decoder = 'h264_cuvid'
      config.options = { resize: '1280x720' }
    })

    const form = useDecodeForm()
    form.setDecodeProfile('hevc_qsv')

    expect(presetStore.draftPreset.decodeConfig).toMatchObject({
      mode: 'hardware',
      hwaccel: 'qsv',
      hwaccelDevice: 'qsv0',
      decoder: 'hevc_qsv',
      options: { load_plugin: 'hevc_hw' },
    })
  })

  it('switches the device number to the first probed option when the hardware device type changes', () => {
    const presetStore = usePresetStore()
    const form = useDecodeForm()

    form.setDecodeProfile('h264_cuvid')
    presetStore.patchDecode((config) => {
      config.hwaccelDevice = '0'
    })

    form.setDecodeHwaccel('d3d11va')

    expect(presetStore.draftPreset.decodeConfig.hwaccel).toBe('d3d11va')
    expect(presetStore.draftPreset.decodeConfig.hwaccelDevice).toBe('d3d11-0')
  })

  it('exposes probed device number options and applies the selected option', () => {
    const presetStore = usePresetStore()
    const form = useDecodeForm()

    form.setDecodeProfile('h264_cuvid')

    expect(form.decoderHardwareDeviceNumberOptions.value).toEqual([
      { value: '0', label: '0' },
      { value: '1', label: '1' },
    ])

    form.setDecodeHwaccelDevice('1')

    expect(presetStore.draftPreset.decodeConfig.hwaccelDevice).toBe('1')
  })

  it('falls back to software when selecting a profile without verified devices', () => {
    const form = useDecodeForm()

    form.setDecodeProfile('av1_cuvid')

    expect(form.decoderHardwareDeviceOptions.value).toEqual([])
    expect(usePresetStore().draftPreset.decodeConfig).toMatchObject({
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
    })
  })

  it('normalizes a stale hardware decoder without verified devices back to software', async () => {
    const presetStore = usePresetStore()
    presetStore.patchDecode((config) => {
      config.mode = 'hardware'
      config.hwaccel = ''
      config.hwaccelDevice = ''
      config.decoder = 'av1_cuvid'
      config.options = {}
    })

    useDecodeForm()
    await nextTick()

    expect(presetStore.draftPreset.decodeConfig).toMatchObject({
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
    })
  })
})
