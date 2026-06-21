import { describe, expect, it } from 'vitest'

import { normalizeDecodeConfig, resolveDecoderHwaccel } from './normalize'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { DecodeConfig } from '@/types/protocol'

const decoderProfile = (
  name: string,
  label: string,
  family: 'software' | 'nvidia' | 'intel',
  codec: string,
  hardwareDevices: string[],
) => ({
  name,
  label,
  family,
  codec,
  available: true,
  pixelFormats: [],
  hardwareDevices,
  options: [
    {
      name: 'resize',
      label: 'resize',
      type: 'string' as const,
      defaultValue: '1920x1080',
      choices: [],
      min: null,
      max: null,
    },
  ],
})

const makeEnv = (decoderProfiles: EnvironmentCheckResult['ffmpeg']['decoderProfiles']): EnvironmentCheckResult => ({
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: ['cuda', 'qsv', 'd3d11va'],
    encoderProfiles: [],
    decoderProfiles,
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

const baseDecodeConfig = (overrides: Partial<DecodeConfig> = {}): DecodeConfig => ({
  mode: 'hardware',
  hwaccel: 'cuda',
  hwaccelDevice: '0',
  decoder: 'h264_cuvid',
  options: {},
  ...overrides,
})

describe('resolveDecoderHwaccel', () => {
  it('keeps a supported cached device and otherwise falls back to the first verified device', () => {
    const profile = decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['d3d11va', 'cuda'])

    expect(resolveDecoderHwaccel(profile, 'cuda')).toBe('cuda')
    expect(resolveDecoderHwaccel(profile, 'qsv')).toBe('d3d11va')
  })

  it('returns an empty value when FFmpeg did not verify any hardware device', () => {
    const profile = decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', [])

    expect(resolveDecoderHwaccel(profile, 'cuda')).toBe('')
  })
})

describe('normalizeDecodeConfig decoder hardware devices', () => {
  it('preserves supported cached hwaccel and device number', () => {
    const env = makeEnv([
      decoderProfile('software', 'Software Decode', 'software', 'any', []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['d3d11va', 'cuda']),
    ])

    expect(normalizeDecodeConfig(baseDecodeConfig(), env, 'h264')).toMatchObject({
      mode: 'hardware',
      decoder: 'h264_cuvid',
      hwaccel: 'cuda',
      hwaccelDevice: '0',
      options: { resize: '1920x1080' },
    })
  })

  it('resets unsupported cached hwaccel to the first verified device and clears the old device number', () => {
    const env = makeEnv([
      decoderProfile('software', 'Software Decode', 'software', 'any', []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['d3d11va']),
    ])

    expect(normalizeDecodeConfig(baseDecodeConfig(), env, 'h264')).toMatchObject({
      mode: 'hardware',
      decoder: 'h264_cuvid',
      hwaccel: 'd3d11va',
      hwaccelDevice: '',
    })
  })

  it('does not infer cuda or qsv when the decoder profile has no verified devices', () => {
    const env = makeEnv([
      decoderProfile('software', 'Software Decode', 'software', 'any', []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', []),
    ])

    expect(normalizeDecodeConfig(baseDecodeConfig(), env, 'h264')).toMatchObject({
      mode: 'hardware',
      decoder: 'h264_cuvid',
      hwaccel: '',
      hwaccelDevice: '',
    })
  })
})
