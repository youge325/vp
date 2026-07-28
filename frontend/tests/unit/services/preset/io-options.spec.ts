import { describe, expect, it } from 'vitest'

import {
  buildProfileOptions,
  CONTAINER_SELECT_OPTIONS,
} from '@/services/preset/io-options'
import type { DecoderProfileSpec, EncoderProfileSpec } from '@/types/protocol'

const decoderProfile = (name: string, label: string): DecoderProfileSpec => ({
  name,
  label,
  family: 'software',
  codec: 'any',
  available: true,
  hardwareDevices: [],
  options: [],
})

const encoderProfile = (name: string, label: string): EncoderProfileSpec => ({
  name,
  label,
  family: 'software',
  codec: 'h264',
  available: true,
  hardwareDevices: [],
  options: [],
})

describe('io-options', () => {
  it('builds profile select options for decoder and encoder profiles', () => {
    expect(buildProfileOptions([
      decoderProfile('software', 'Software Decode'),
      encoderProfile('hevc_nvenc', 'NVENC H.265'),
    ])).toEqual([
      { value: 'software', label: 'Software Decode' },
      { value: 'hevc_nvenc', label: 'NVENC H.265' },
    ])
  })

  it('exposes uppercase container select options', () => {
    expect(CONTAINER_SELECT_OPTIONS).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])
  })
})
