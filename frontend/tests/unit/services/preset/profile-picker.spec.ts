import { describe, expect, it } from 'vitest'
import {
  getVisibleEncoderProfiles,
  getVisibleDecoderProfiles,
  pickPreferredDecoderProfile,
} from '@/services/preset/profile-picker'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function makeEnv(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return createEnvironmentResult(overrides)
}

type DecoderProfile = EnvironmentCheckResult['ffmpeg']['decoderProfiles'][number]

function decoderProfile(
  name: string,
  family: DecoderProfile['family'],
  codec: string,
  hardwareDevices: string[] = [],
): DecoderProfile {
  return {
    name,
    available: true,
    family,
    codec,
    label: name,
    hardwareDevices,
    options: [],
  }
}

function decoderEnvironment(decoderProfiles: DecoderProfile[]): EnvironmentCheckResult {
  return createEnvironmentResult({
    ffmpeg: {
      decoderProfiles,
      encoderProfiles: [],
      hwaccels: ['cuda'],
    },
  })
}

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
    const env = decoderEnvironment([
      decoderProfile('software', 'software', 'any'),
      decoderProfile('hevc_cuvid', 'nvidia', 'hevc'),
      decoderProfile('h264_cuvid', 'nvidia', 'h264', ['cuda']),
    ])

    expect(getVisibleDecoderProfiles(env, 'hevc').map((profile) => profile.name)).toEqual(['software'])
    expect(getVisibleDecoderProfiles(env, 'h264').map((profile) => profile.name)).toEqual([
      'software',
      'h264_cuvid',
    ])
  })

  it('falls back to software when the matching hardware decoder has no verified devices', () => {
    const env = decoderEnvironment([
      decoderProfile('software', 'software', 'any'),
      decoderProfile('hevc_cuvid', 'nvidia', 'hevc'),
    ])

    expect(pickPreferredDecoderProfile(env, 'hevc')?.name).toBe('software')
  })
})
