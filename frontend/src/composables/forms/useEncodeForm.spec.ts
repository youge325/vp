import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEncodeForm } from './useEncodeForm'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { CapabilityOptionSpec } from '@/types/domain/capability'
import type { EnvironmentCheckResult } from '@/types/domain/env'

const option = (
  name: string,
  defaultValue: string,
  choices: Array<{ label: string; value: string }> = [],
): CapabilityOptionSpec => ({
  name,
  label: name,
  type: choices.length ? 'choice' : 'string',
  defaultValue,
  choices,
  min: null,
  max: null,
})

const makeEnv = (): EnvironmentCheckResult => ({
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: [],
    decoderProfiles: [],
    encoderProfiles: [
      {
        name: 'libx265',
        label: 'x265',
        family: 'software',
        codec: 'hevc',
        available: true,
        pixelFormats: [],
        hardwareDevices: [],
        options: [option('preset', 'medium')],
        rateControlModes: [{ mode: 'crf', label: 'CRF', defaultValue: 18, unit: 'CRF' }],
      },
      {
        name: 'hevc_nvenc',
        label: 'NVENC H.265',
        family: 'nvidia',
        codec: 'hevc',
        available: true,
        pixelFormats: [],
        hardwareDevices: [],
        options: [option('preset', 'p5'), option('tune', 'hq')],
        rateControlModes: [{ mode: 'cq', label: 'CQ', defaultValue: 24, unit: 'CQ' }],
      },
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

describe('useEncodeForm profile binding', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-06-21T00:00:00Z',
    )
  })

  it('selects encoder profile through pure profile rules', () => {
    const presetStore = usePresetStore()
    presetStore.patchEncode((config) => {
      config.codec = 'libx265'
      config.family = 'cpu'
      config.rateControl = { mode: 'crf', value: 20 }
      config.options = { preset: 'slow', stale: true }
    })

    const form = useEncodeForm()
    form.setEncodeProfile('hevc_nvenc')

    expect(presetStore.draftPreset.encodeConfig).toMatchObject({
      codec: 'hevc_nvenc',
      family: 'nvidia',
      rateControl: { mode: 'cq', value: 24 },
      options: { preset: 'slow', tune: 'hq' },
    })
  })

  it('updates encoder options immutably through pure option rules', () => {
    const presetStore = usePresetStore()
    const form = useEncodeForm()

    const previous = presetStore.draftPreset.encodeConfig.options
    form.setEncodeOption('preset', 'p7')

    expect(presetStore.draftPreset.encodeConfig.options).toEqual({ preset: 'p7' })
    expect(presetStore.draftPreset.encodeConfig.options).not.toBe(previous)
  })
})
