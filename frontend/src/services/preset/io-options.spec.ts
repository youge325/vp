import { describe, expect, it } from 'vitest'

import {
  buildContainerOptions,
  buildProfileOptions,
  CONTAINER_SELECT_OPTIONS,
  toNumberValue,
  toRateControlMode,
} from './io-options'
import type { DecoderProfileSpec, EncoderProfileSpec } from '@/types/domain/capability'

const decoderProfile = (name: string, label: string): DecoderProfileSpec => ({
  name,
  label,
  family: 'software',
  codec: 'any',
  available: true,
  pixelFormats: [],
  hardwareDevices: [],
  options: [],
})

const encoderProfile = (name: string, label: string): EncoderProfileSpec => ({
  name,
  label,
  family: 'software',
  codec: 'h264',
  available: true,
  pixelFormats: [],
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

  it('builds uppercase container select options', () => {
    expect(buildContainerOptions(['mp4', 'mkv', 'mov'])).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])
    expect(CONTAINER_SELECT_OPTIONS).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])
  })

  it('converts select values to domain values used by encode form setters', () => {
    expect(toRateControlMode('cq')).toBe('cq')
    expect(toRateControlMode('bitrate')).toBe('bitrate')
  })

  it('preserves existing BaseNumber model-value conversion semantics', () => {
    expect(toNumberValue(1000)).toBe(1000)
    expect(toNumberValue('24')).toBe(24)
    expect(Number.isNaN(toNumberValue(undefined))).toBe(true)
  })
})
