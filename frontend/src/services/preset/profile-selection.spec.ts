import { describe, expect, it } from 'vitest'

import {
  defaultRateControlValue,
  fallbackUnavailableDecodeProfile,
  selectDecodeProfile,
  selectEncodeProfile,
} from './profile-selection'
import type {
  CapabilityOptionSpec,
  DecoderProfileSpec,
  EncoderProfileSpec,
  HardwareDeviceOptionSpec,
} from '@/types/domain/capability'
import type { EncodeConfig } from '@/types/protocol'

const stringOption = (name: string, defaultValue: string): CapabilityOptionSpec => ({
  name,
  label: name,
  type: 'string',
  defaultValue,
  choices: [],
  min: null,
  max: null,
})

const decoderProfile = (
  overrides: Partial<DecoderProfileSpec> = {},
  hardwareDeviceOptions: Record<string, HardwareDeviceOptionSpec[]> = {
    cuda: [
      { value: '0', label: '0' },
      { value: '1', label: '1' },
    ],
  },
): DecoderProfileSpec => ({
  name: 'h264_cuvid',
  label: 'NVDEC H.264',
  family: 'nvidia',
  codec: 'h264',
  available: true,
  pixelFormats: [],
  hardwareDevices: ['cuda', 'd3d11va'],
  hardwareDeviceOptions,
  options: [stringOption('resize', '1920x1080')],
  ...overrides,
})

const encoderProfile = (overrides: Partial<EncoderProfileSpec> = {}): EncoderProfileSpec => ({
  name: 'hevc_nvenc',
  label: 'NVENC H.265',
  family: 'nvidia',
  codec: 'hevc',
  available: true,
  pixelFormats: [],
  hardwareDevices: [],
  options: [stringOption('preset', 'p5')],
  rateControlModes: [{ mode: 'cq', label: 'CQ', defaultValue: 24, unit: 'CQ' }],
  ...overrides,
})

const encodeConfig = (): EncodeConfig => ({
  codec: 'libx265',
  family: 'cpu',
  container: 'mp4',
  keepAudio: true,
  rateControl: { mode: 'crf', value: 18 },
  options: { preset: 'medium' },
})

describe('profile-selection rules', () => {
  it('selects a hardware decoder with preferred device values and seeded options', () => {
    expect(selectDecodeProfile(decoderProfile(), { resize: '1280x720' }, 'd3d11va')).toEqual({
      mode: 'hardware',
      hwaccel: 'd3d11va',
      hwaccelDevice: '',
      decoder: 'h264_cuvid',
      options: { resize: '1280x720' },
    })
  })

  it('falls back stale hardware decoder selection to software config', () => {
    expect(fallbackUnavailableDecodeProfile(null, 'hardware')).toEqual({
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
      options: {},
    })
    expect(fallbackUnavailableDecodeProfile(decoderProfile(), 'hardware')).toBeNull()
    expect(fallbackUnavailableDecodeProfile(null, 'software')).toBeNull()
  })

  it('selects an encoder profile while preserving container fields and seeding options', () => {
    expect(selectEncodeProfile(encoderProfile(), encodeConfig())).toEqual({
      codec: 'hevc_nvenc',
      family: 'nvidia',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'cq', value: 24 },
      options: { preset: 'medium' },
    })
  })

  it('keeps current rate control when selected encoder has no probed modes', () => {
    expect(
      selectEncodeProfile(encoderProfile({ family: 'software', rateControlModes: [] }), encodeConfig()),
    ).toMatchObject({
      codec: 'hevc_nvenc',
      family: 'cpu',
      rateControl: { mode: 'crf', value: 18 },
    })
  })

  it('returns canonical default rate control values by encoder family', () => {
    expect(defaultRateControlValue('nvidia')).toEqual({ mode: 'cq', value: 23 })
    expect(defaultRateControlValue('intel')).toEqual({ mode: 'qp', value: 23 })
    expect(defaultRateControlValue('cpu')).toEqual({ mode: 'crf', value: 18 })
  })
})
