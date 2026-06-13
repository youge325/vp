import { describe, expect, it } from 'vitest'
import {
  getRateControlModeOptions,
  getRateControlUnit,
  hasRateControlModes,
  resolveRateControlForMode,
  resolveRateControlForProfile,
} from './rate-control'
import type { EncoderProfileSpec } from '@/types/domain/capability'

function makeProfile(overrides: Partial<EncoderProfileSpec> = {}): EncoderProfileSpec {
  return {
    name: 'h264_nvenc',
    label: 'NVENC H.264',
    family: 'nvidia',
    codec: 'h264',
    available: true,
    pixelFormats: [],
    hardwareDevices: [],
    options: [
      { name: 'crf', label: 'crf', type: 'number', defaultValue: 18, choices: [], min: 0, max: 51 },
    ],
    ...overrides,
  }
}

describe('rate control profile helpers', () => {
  it('uses only backend-probed rateControlModes instead of profile options', () => {
    const profile = makeProfile({
      rateControlModes: [
        { mode: 'cq', label: 'CQ', defaultValue: 21, unit: 'CQ' },
        { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
      ],
    })

    expect(getRateControlModeOptions(profile)).toEqual([
      { value: 'cq', label: 'CQ' },
      { value: 'bitrate', label: 'Bitrate' },
    ])
  })

  it('resolves the first probed mode as the profile default', () => {
    const profile = makeProfile({
      rateControlModes: [
        { mode: 'qp', label: 'QP', defaultValue: 25, unit: 'QP' },
        { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
      ],
    })

    expect(resolveRateControlForProfile(profile)).toEqual({ mode: 'qp', value: 25 })
  })

  it('resolves selected mode value and unit from backend metadata', () => {
    const profile = makeProfile({
      rateControlModes: [
        { mode: 'crf', label: 'CRF', defaultValue: 19, unit: 'CRF' },
        { mode: 'bitrate', label: 'Bitrate', defaultValue: 8, unit: 'Mbps' },
      ],
    })

    expect(resolveRateControlForMode(profile, 'bitrate')).toEqual({ mode: 'bitrate', value: 8 })
    expect(getRateControlUnit(profile, 'bitrate')).toBe('Mbps')
    expect(getRateControlUnit(profile, 'crf')).toBe('CRF')
  })

  it('treats missing or empty rateControlModes as unavailable', () => {
    expect(hasRateControlModes(makeProfile())).toBe(false)
    expect(hasRateControlModes(makeProfile({ rateControlModes: [] }))).toBe(false)
    expect(getRateControlModeOptions(makeProfile())).toEqual([])
    expect(resolveRateControlForProfile(makeProfile())).toBeNull()
    expect(resolveRateControlForMode(makeProfile(), 'crf')).toBeNull()
    expect(getRateControlUnit(makeProfile(), 'crf')).toBeNull()
  })
})
