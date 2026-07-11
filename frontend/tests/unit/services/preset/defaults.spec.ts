import { describe, expect, it } from 'vitest'

import * as presetDefaults from '@/services/preset/defaults'
import { createDefaultDecodeConfig, createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { HardwareDeviceOptionSpec } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

const makeEnv = (decoderProfiles: EnvironmentCheckResult['ffmpeg']['decoderProfiles']): EnvironmentCheckResult => createEnvironmentResult({
  ffmpeg: {
    available: true,
    hwaccels: ['cuda', 'qsv', 'd3d11va'],
    encoderProfiles: [],
    decoderProfiles,
  },
})

const decoderProfile = (
  name: string,
  label: string,
  family: 'software' | 'nvidia' | 'intel',
  codec: string,
  hardwareDevices: string[],
  hardwareDeviceOptions: Record<string, HardwareDeviceOptionSpec[]> = {},
) => ({
  name,
  label,
  family,
  codec,
  available: true,
  hardwareDevices,
  hardwareDeviceOptions,
  options: [],
})

describe('preset defaults public surface', () => {
  it('keeps output config defaults private to the workbench preset factory', () => {
    expect('createDefaultOutputConfig' in presetDefaults).toBe(false)
  })

  it('creates default output config through the workbench preset factory', () => {
    expect(createDefaultWorkbenchPreset(null).outputConfig).toEqual({
      outputDir: null,
      openOnComplete: true,
      segmentFrames: 1000,
    })
  })
})

describe('createDefaultDecodeConfig decoder hardware devices', () => {
  it('uses the first FFmpeg-verified hardware device from the selected decoder profile', () => {
    const env = makeEnv([
      decoderProfile('software', 'Software Decode', 'software', 'any', []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', ['d3d11va', 'cuda'], {
        d3d11va: [{ value: 'd3d11-0', label: 'D3D11 0' }],
        cuda: [{ value: '0', label: '0' }],
      }),
    ])

    expect(createDefaultDecodeConfig(env, 'h264')).toMatchObject({
      mode: 'hardware',
      decoder: 'h264_cuvid',
      hwaccel: 'd3d11va',
      hwaccelDevice: 'd3d11-0',
    })
  })

  it('falls back to software when the selected decoder profile has no verified devices', () => {
    const env = makeEnv([
      decoderProfile('software', 'Software Decode', 'software', 'any', []),
      decoderProfile('h264_cuvid', 'NVDEC H.264', 'nvidia', 'h264', []),
    ])

    expect(createDefaultDecodeConfig(env, 'h264')).toMatchObject({
      mode: 'software',
      decoder: 'software',
      hwaccel: '',
      hwaccelDevice: '',
    })
  })
})
