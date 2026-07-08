import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import EncodeModuleView from './EncodeModuleView.vue'
import { useEnvStore } from '@/stores/env'
import type { EncoderProfileSpec } from '@/types/domain/capability'
import type { EnvironmentCheckResult } from '@/types/domain/env'

const encoderProfile = (name: string, label: string): EncoderProfileSpec => ({
  name,
  label,
  family: name.includes('nvenc') ? 'nvidia' : 'software',
  codec: 'h264',
  available: true,
  pixelFormats: [],
  hardwareDevices: [],
  options: [],
  rateControlModes: [{ mode: 'crf', label: 'CRF', defaultValue: 18, unit: 'CRF' }],
})

const makeEnv = (): EnvironmentCheckResult => ({
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: [],
    encoderProfiles: [
      encoderProfile('libx264', 'x264'),
      encoderProfile('h264_nvenc', 'NVENC H.264'),
    ],
    decoderProfiles: [],
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

describe('EncodeModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-07-08T00:00:00Z',
    )
  })

  it('renders container and encoder profile options from pure option rules', () => {
    const wrapper = mount(EncodeModuleView)

    expect(wrapper.text()).toContain('MP4')
    expect(wrapper.text()).toContain('MKV')
    expect(wrapper.text()).toContain('x264')
    expect(wrapper.text()).toContain('NVENC H.264')
  })
})
