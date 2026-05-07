import { describe, expect, it } from 'vitest'
import {
  getVisibleEncoderProfiles,
  getVisibleDecoderProfiles,
  pickPreferredEncoderProfile,
} from './profile-picker'
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
    onnxModels: { interpolation: [], super_resolution: [] },
    rifeModel: { available: false },
    ...overrides,
  } as EnvironmentCheckResult
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
})
