import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useDecodeForm } from './useDecodeForm'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { EnvironmentCheckResult } from '@/types/domain/env'

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
  options = [stringOption('resize', '1920x1080')],
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

const makeEnv = (): EnvironmentCheckResult => ({
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: ['cuda', 'qsv', 'd3d11va'],
    encoderProfiles: [],
    decoderProfiles: [
      decoderProfile('software', 'Software Decode', 'software', 'any', [], []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['cuda', 'd3d11va']),
      decoderProfile('hevc_qsv', 'QSV H.265', 'intel', 'hevc', ['qsv'], [stringOption('load_plugin', 'hevc_hw')]),
      decoderProfile('av1_cuvid', 'NVDEC AV1', 'nvidia', 'av1', []),
    ],
  },
  gpu: { available: true, devices: ['GPU'], adapters: [] },
  tensorBackends: { pytorch: false, paddle: false, onnx: false },
  tensorEngines: {},
  onnxRuntime: { available: false, providers: [] },
  rifeModel: { available: false },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  animeProfiles: [],
})

describe('useDecodeForm decoder hardware devices', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-06-21T00:00:00Z',
    )
  })

  it('switches decoder profile to the first verified hardware device and clears the old device number', () => {
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
      hwaccelDevice: '',
      decoder: 'hevc_qsv',
      options: { load_plugin: 'hevc_hw' },
    })
  })

  it('clears the device number when the hardware device type changes', () => {
    const presetStore = usePresetStore()
    const form = useDecodeForm()

    form.setDecodeProfile('h264_cuvid')
    presetStore.patchDecode((config) => {
      config.hwaccelDevice = '0'
    })

    form.setDecodeHwaccel('d3d11va')

    expect(presetStore.draftPreset.decodeConfig.hwaccel).toBe('d3d11va')
    expect(presetStore.draftPreset.decodeConfig.hwaccelDevice).toBe('')
  })

  it('exposes an empty device list for profiles without verified devices', () => {
    const form = useDecodeForm()

    form.setDecodeProfile('av1_cuvid')

    expect(form.decoderHardwareDeviceOptions.value).toEqual([])
    expect(usePresetStore().draftPreset.decodeConfig.hwaccel).toBe('')
  })
})
