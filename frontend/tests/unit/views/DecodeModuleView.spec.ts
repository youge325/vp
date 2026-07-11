import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import DecodeModuleView from '@/views/DecodeModuleView.vue'
import { useEnvStore } from '@/stores/env'
import type { DecoderProfileSpec } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentPayload, createEnvironmentResult } from '../fixtures/environment'

const decoderProfile = (name: string, label: string): DecoderProfileSpec => ({
  name,
  label,
  family: name === 'software' ? 'software' : 'nvidia',
  codec: 'h264',
  available: true,
  hardwareDevices: name === 'software' ? [] : ['cuda'],
  hardwareDeviceOptions: {},
  options: [],
})

const makeEnv = (): EnvironmentCheckResult => createEnvironmentResult({
  ffmpeg: {
    available: true,
    hwaccels: ['cuda'],
    encoderProfiles: [],
    decoderProfiles: [
      decoderProfile('software', 'Software Decode'),
      decoderProfile('h264_cuvid', 'NVDEC H.264'),
    ],
  },
  gpu: { adapters: [] },
  tensorEngines: { pytorch: [], paddle: [], onnx: [] },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  runtimeMode: 'external',
})

describe('DecodeModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(makeEnv()))
  })

  it('renders decoder profile options from pure option rules', () => {
    const wrapper = mount(DecodeModuleView)

    expect(wrapper.text()).toContain('Software Decode')
    expect(wrapper.text()).toContain('NVDEC H.264')
  })
})
