import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDecodeHardwareBindings } from '@/composables/forms/decode-hardware-bindings'
import type { DecoderProfileSpec, HardwareDeviceOptionSpec } from '@/types/domain/capability'
import type { DecodeConfig, WorkbenchPreset } from '@/types/protocol'

const stringOption = (name: string, defaultValue: string) => ({
  name,
  label: name,
  type: 'string' as const,
  defaultValue,
  choices: [],
  min: null,
  max: null,
})

function decoderProfile(
  hardwareDevices: string[],
  hardwareDeviceOptions: Record<string, HardwareDeviceOptionSpec[]>,
): DecoderProfileSpec {
  return {
    name: 'h264_cuvid',
    label: 'NVDEC H.264',
    family: 'nvidia',
    codec: 'h264',
    available: true,
    hardwareDevices,
    hardwareDeviceOptions,
    options: [stringOption('resize', '1920x1080')],
  }
}

function makeBindings() {
  const currentDecoderProfile = ref<DecoderProfileSpec | null>(
    decoderProfile(['cuda', 'd3d11va'], {
      cuda: [
        { value: '0', label: '0' },
        { value: '1', label: '1' },
      ],
      d3d11va: [{ value: 'd3d11-0', label: 'D3D11 0' }],
    }),
  )
  const editorConfig = reactive({
    decodeConfig: {
      mode: 'hardware',
      hwaccel: 'cuda',
      hwaccelDevice: '0',
      decoder: 'h264_cuvid',
      options: {},
    },
  } as WorkbenchPreset)
  const bindings = createDecodeHardwareBindings({
    currentDecoderProfile: computed(() => currentDecoderProfile.value),
    editorConfig: computed(() => editorConfig),
    patchDecode: (mutator: (config: DecodeConfig) => void) => {
      mutator(editorConfig.decodeConfig)
    },
  })
  return { bindings, currentDecoderProfile, editorConfig }
}

describe('decode hardware bindings', () => {
  it('derives hardware device and probed device-number options from the current profile', () => {
    const { bindings } = makeBindings()

    expect(bindings.decoderHardwareDeviceOptions.value).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'd3d11va', label: 'D3D11VA' },
    ])
    expect(bindings.decoderHardwareDeviceNumberOptions.value).toEqual([
      { value: '0', label: '0' },
      { value: '1', label: '1' },
    ])
  })

  it('applies hwaccel and device selections through patchDecode', () => {
    const { bindings, editorConfig } = makeBindings()

    bindings.setDecodeHwaccel('d3d11va')
    bindings.setDecodeHwaccelDevice('d3d11-0')

    expect(editorConfig.decodeConfig).toMatchObject({
      mode: 'hardware',
      hwaccel: 'd3d11va',
      hwaccelDevice: 'd3d11-0',
      decoder: 'h264_cuvid',
    })
  })

  it('returns empty options when no hardware profile is selected', () => {
    const { bindings, currentDecoderProfile } = makeBindings()

    currentDecoderProfile.value = null

    expect(bindings.decoderHardwareDeviceOptions.value).toEqual([])
    expect(bindings.decoderHardwareDeviceNumberOptions.value).toEqual([])
  })
})
