import { describe, expect, it } from 'vitest'
import * as profilePicker from '@/services/preset/profile-picker'
import {
  getVisibleEncoderProfiles,
  getVisibleDecoderProfiles,
  pickPreferredEncoderProfile,
  pickPreferredDecoderProfile,
} from '@/services/preset/profile-picker'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: false, devices: [], adapters: [] },
    tensorBackends: {},
    tensorEngines: {},
    onnxRuntime: { available: false, providers: [] },
    rifeModel: { available: false },
    ...overrides,
  } as EnvironmentCheckResult
}

describe('profile-picker public surface', () => {
  it('does not expose internal raw profile and codec helpers', () => {
    expect('getEncoderProfiles' in profilePicker).toBe(false)
    expect('getDecoderProfiles' in profilePicker).toBe(false)
    expect('normalizeCodec' in profilePicker).toBe(false)
  })
})

describe('getVisibleEncoderProfiles', () => {
  it('filters out unavailable profiles', () => {
    const env = makeEnv({
      ffmpeg: {
        encoderProfiles: [
          { name: 'libx265', available: true, family: 'cpu', codec: 'hevc', label: 'HEVC', options: [] },
          { name: 'h264_nvenc', available: false, family: 'nvidia', codec: 'h264', label: 'NVENC H264', options: [] },
        ],
        decoderProfiles: [],
        hwaccels: [],
      },
    } as any)
    const profiles = getVisibleEncoderProfiles(env)
    expect(profiles).toHaveLength(1)
    expect(profiles[0].name).toBe('libx265')
  })
})

describe('getVisibleDecoderProfiles', () => {
  it('filters by video codec when provided', () => {
    const env = makeEnv({
      ffmpeg: {
        decoderProfiles: [
          { name: 'hevc', available: true, family: 'software', codec: 'hevc', label: 'HEVC', options: [] },
          { name: 'h264', available: true, family: 'software', codec: 'h264', label: 'H264', options: [] },
        ],
        encoderProfiles: [],
        hwaccels: [],
      },
    } as any)
    const profiles = getVisibleDecoderProfiles(env, 'hevc')
    expect(profiles).toHaveLength(1)
    expect(profiles[0].name).toBe('hevc')
  })

  it('filters out hardware decoder profiles without verified hardware devices', () => {
    const env = makeEnv({
      ffmpeg: {
        decoderProfiles: [
          { name: 'software', available: true, family: 'software', codec: 'any', label: 'Software', options: [] },
          {
            name: 'hevc_cuvid',
            available: true,
            family: 'nvidia',
            codec: 'hevc',
            label: 'NVDEC HEVC',
            hardwareDevices: [],
            options: [],
          },
          {
            name: 'h264_cuvid',
            available: true,
            family: 'nvidia',
            codec: 'h264',
            label: 'NVDEC H264',
            hardwareDevices: ['cuda'],
            options: [],
          },
        ],
        encoderProfiles: [],
        hwaccels: ['cuda'],
      },
    } as any)

    expect(getVisibleDecoderProfiles(env, 'hevc').map((profile) => profile.name)).toEqual(['software'])
    expect(getVisibleDecoderProfiles(env, 'h264').map((profile) => profile.name)).toEqual([
      'software',
      'h264_cuvid',
    ])
  })

  it('falls back to software when the matching hardware decoder has no verified devices', () => {
    const env = makeEnv({
      ffmpeg: {
        decoderProfiles: [
          { name: 'software', available: true, family: 'software', codec: 'any', label: 'Software', options: [] },
          {
            name: 'hevc_cuvid',
            available: true,
            family: 'nvidia',
            codec: 'hevc',
            label: 'NVDEC HEVC',
            hardwareDevices: [],
            options: [],
          },
        ],
        encoderProfiles: [],
        hwaccels: ['cuda'],
      },
    } as any)

    expect(pickPreferredDecoderProfile(env, 'hevc')?.name).toBe('software')
  })
})
