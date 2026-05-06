import { describe, expect, it } from 'vitest'
import {
  getVisibleEncoderProfiles,
  getVisibleDecoderProfiles,
  resolvePrimaryMode,
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

describe('resolvePrimaryMode', () => {
  it('returns frame_interpolation when interpolation is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: true },
        superResolution: { enabled: false },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('frame_interpolation')
  })

  it('returns super_resolution when only sr is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: true },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('super_resolution')
  })

  it('returns anime_optimization when only anime is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: false },
        anime: { enabled: true },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('anime_optimization')
  })

  it('returns format_conversion when nothing is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: false },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('format_conversion')
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
})
