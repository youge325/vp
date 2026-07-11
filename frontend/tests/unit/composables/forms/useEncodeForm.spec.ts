import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEncodeForm } from '@/composables/forms/useEncodeForm'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { CapabilityOptionSpec } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentPayload, createEnvironmentResult } from '../../fixtures/environment'

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

const makeEnv = (): EnvironmentCheckResult => createEnvironmentResult({
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
        hardwareDevices: [],
        options: [option('preset', 'p5'), option('tune', 'hq')],
        rateControlModes: [{ mode: 'cq', label: 'CQ', defaultValue: 24, unit: 'CQ' }],
      },
    ],
  },
  gpu: { adapters: [] },
  tensorEngines: { pytorch: [], paddle: [], onnx: [] },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  runtimeMode: 'external',
})

describe('useEncodeForm profile binding', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(makeEnv()))
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
