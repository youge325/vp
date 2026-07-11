import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import EncodeModuleView from '@/views/EncodeModuleView.vue'
import { useEnvStore } from '@/stores/env'
import type { EncoderProfileSpec } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentPayload, createEnvironmentResult } from '../fixtures/environment'

const encoderProfile = (name: string, label: string): EncoderProfileSpec => ({
  name,
  label,
  family: name.includes('nvenc') ? 'nvidia' : 'software',
  codec: 'h264',
  available: true,
  hardwareDevices: [],
  options: [],
  rateControlModes: [{ mode: 'crf', label: 'CRF', defaultValue: 18, unit: 'CRF' }],
})

const makeEnv = (): EnvironmentCheckResult => createEnvironmentResult({
  ffmpeg: {
    available: true,
    hwaccels: [],
    encoderProfiles: [
      encoderProfile('libx264', 'x264'),
      encoderProfile('h264_nvenc', 'NVENC H.264'),
    ],
    decoderProfiles: [],
  },
  gpu: { adapters: [] },
  tensorEngines: { pytorch: [], paddle: [], onnx: [] },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  runtimeMode: 'external',
})

describe('EncodeModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(makeEnv()))
  })

  it('renders container and encoder profile options from pure option rules', () => {
    const wrapper = mount(EncodeModuleView)

    expect(wrapper.text()).toContain('MP4')
    expect(wrapper.text()).toContain('MKV')
    expect(wrapper.text()).toContain('x264')
    expect(wrapper.text()).toContain('NVENC H.264')
  })
})
