import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEncodeForm } from '@/composables/forms/useEncodeForm'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import {
  createEncodingEnvironment,
  createEnvironmentPayload,
} from '../../fixtures/environment'

describe('useEncodeForm profile binding', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(createEncodingEnvironment()))
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

  it('assembles profile, rate-control, container, and output bindings in one root', () => {
    const presetStore = usePresetStore()
    const form = useEncodeForm()

    expect(form.encoderProfileOptions.value).toEqual([
      { value: 'libx265', label: 'x265' },
      { value: 'hevc_nvenc', label: 'NVENC H.265' },
    ])
    expect(form.rateControlOptions.value).toEqual([{ value: 'crf', label: 'CRF' }])
    expect(form.containerOptions).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])

    form.setContainer('mkv')
    form.setKeepAudio(false)
    form.setOutputDir('  D:/Video Output  ')
    form.setOpenOnComplete(false)
    form.setSegmentFrames(Number.NaN)

    expect(presetStore.draftPreset.encodeConfig).toMatchObject({
      container: 'mkv',
      keepAudio: false,
    })
    expect(presetStore.draftPreset.outputConfig).toEqual({
      outputDir: 'D:/Video Output',
      openOnComplete: false,
      segmentFrames: 1000,
    })
  })
})
