import { computed, nextTick, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultDecodeConfig } from '@/services/preset/defaults'
import { createDecodeFormBindings } from './decode-form-bindings'
import type { HardwareDeviceOptionSpec } from '@/types/domain/capability'
import type { EnvironmentCheckResult } from '@/types/domain/env'
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
  pixelFormats: [],
  hardwareDevices,
  hardwareDeviceOptions,
  options,
})

function makeEnv(): EnvironmentCheckResult {
  return {
    type: 'check',
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
    gpu: { available: true, devices: ['GPU'], adapters: [] },
    tensorBackends: { pytorch: false, paddle: false, onnx: false },
    tensorEngines: {},
    onnxRuntime: { available: false, providers: [] },
    rifeModel: { available: false },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    animeProfiles: [],
  }
}

function makeBindings() {
  const checkResult = ref<EnvironmentCheckResult | null>(makeEnv())
  const editorConfig = reactive({
    decodeConfig: createDefaultDecodeConfig(checkResult.value),
  } as WorkbenchPreset)
  const editorVideoCodec = ref('h264')
  const bindings = createDecodeFormBindings({
    checkResult: computed(() => checkResult.value),
    editorConfig: computed(() => editorConfig),
    editorVideoCodec: computed(() => editorVideoCodec.value),
    patchDecode: (mutator: (config: DecodeConfig) => void) => { mutator(editorConfig.decodeConfig) },
  })

  return { bindings, checkResult, editorConfig, editorVideoCodec }
}

describe('decode form bindings', () => {
  it('derives decoder profiles, hardware device options, and profile options', () => {
    const { bindings } = makeBindings()

    bindings.setDecodeProfile('h264_cuvid')

    expect(bindings.visibleDecoderProfiles.value.map((profile) => profile.name)).toEqual(['software', 'h264_cuvid'])
    expect(bindings.decoderProfileOptions.value).toEqual([
      { value: 'software', label: 'Software Decode' },
      { value: 'h264_cuvid', label: 'NVDEC H.264' },
    ])
    expect(bindings.currentDecoderProfile.value?.name).toBe('h264_cuvid')
    expect(bindings.decoderOptions.value.map((option) => option.name)).toEqual(['resize'])
    expect(bindings.decoderHardwareDeviceOptions.value).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'd3d11va', label: 'D3D11VA' },
    ])
    expect(bindings.decoderHardwareDeviceNumberOptions.value).toEqual([
      { value: '0', label: '0' },
      { value: '1', label: '1' },
    ])
  })

  it('applies decoder profile, hwaccel, device, and option setters through patchDecode', () => {
    const { bindings, editorConfig } = makeBindings()

    bindings.setDecodeProfile('h264_cuvid')
    bindings.setDecodeHwaccel('d3d11va')
    bindings.setDecodeHwaccelDevice('d3d11-0')
    bindings.setDecodeOption('resize', '1280x720')

    expect(editorConfig.decodeConfig).toMatchObject({
      mode: 'hardware',
      hwaccel: 'd3d11va',
      hwaccelDevice: 'd3d11-0',
      decoder: 'h264_cuvid',
      options: { resize: '1280x720' },
    })
    expect(bindings.getDecodeOption(bindings.decoderOptions.value[0])).toBe('1280x720')
  })

  it('watches stale unavailable hardware profile and falls back to software', async () => {
    const { bindings, editorConfig } = makeBindings()

    editorConfig.decodeConfig = {
      mode: 'hardware',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'av1_cuvid',
      options: {},
    }
    await nextTick()

    expect(bindings.currentDecoderProfile.value?.name).toBe('software')
    expect(editorConfig.decodeConfig).toMatchObject({
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
    })
  })
})
