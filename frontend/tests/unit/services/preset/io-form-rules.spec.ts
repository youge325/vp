import { describe, expect, it } from 'vitest'

import {
  applyDecodeHwaccelDeviceSelection,
  applyDecodeHwaccelSelection,
  buildDecoderHardwareDeviceNumberOptions,
  buildDecoderHardwareDeviceOptions,
  buildRateControlViewState,
  normalizeSegmentFrames,
  resolveRateControlModeSelection,
} from '@/services/preset/io-form-rules'
import type { DecoderProfileSpec, EncoderProfileSpec } from '@/types/domain/capability'
import type { DecodeConfig } from '@/types/protocol'

const decoderProfile = (): DecoderProfileSpec => ({
  name: 'h264_cuvid',
  label: 'NVDEC H.264',
  family: 'nvidia',
  codec: 'h264',
  available: true,
  hardwareDevices: ['cuda', 'd3d11va'],
  hardwareDeviceOptions: {
    cuda: [
      { value: '0', label: 'GPU 0' },
      { value: '1', label: 'GPU 1' },
    ],
    d3d11va: [{ value: 'd3d11-0', label: 'D3D11 0' }],
  },
  options: [],
})

const encoderProfile = (): EncoderProfileSpec => ({
  name: 'hevc_nvenc',
  label: 'NVENC H.265',
  family: 'nvidia',
  codec: 'hevc',
  available: true,
  hardwareDevices: [],
  options: [],
  rateControlModes: [
    { mode: 'cq', label: 'CQ', defaultValue: 24, unit: 'CQ' },
    { mode: 'bitrate', label: 'Bitrate', defaultValue: 8000, unit: 'kbps' },
  ],
})

const decodeConfig = (): DecodeConfig => ({
  mode: 'hardware',
  hwaccel: 'cuda',
  hwaccelDevice: '1',
  decoder: 'h264_cuvid',
  options: {},
})

describe('io-form-rules', () => {
  it('builds decoder hardware device options from profile capabilities', () => {
    expect(buildDecoderHardwareDeviceOptions(decoderProfile())).toEqual([
      { value: 'cuda', label: 'CUDA' },
      { value: 'd3d11va', label: 'D3D11VA' },
    ])
    expect(buildDecoderHardwareDeviceOptions(null)).toEqual([])
  })

  it('builds decoder hardware device number options from probed profile details', () => {
    expect(buildDecoderHardwareDeviceNumberOptions(decoderProfile(), 'cuda')).toEqual([
      { value: '0', label: 'GPU 0' },
      { value: '1', label: 'GPU 1' },
    ])
    expect(buildDecoderHardwareDeviceNumberOptions(decoderProfile(), '')).toEqual([])
  })

  it('applies hwaccel selection without mutating the previous decode config', () => {
    const previous = decodeConfig()
    const next = applyDecodeHwaccelSelection(previous, decoderProfile(), 'd3d11va')

    expect(next).toEqual({
      ...previous,
      hwaccel: 'd3d11va',
      hwaccelDevice: 'd3d11-0',
    })
    expect(previous.hwaccel).toBe('cuda')
    expect(previous.hwaccelDevice).toBe('1')
  })

  it('applies hwaccel device selection through available device numbers', () => {
    expect(applyDecodeHwaccelDeviceSelection(decodeConfig(), decoderProfile(), '0')).toMatchObject({
      hwaccel: 'cuda',
      hwaccelDevice: '0',
    })
    expect(applyDecodeHwaccelDeviceSelection(decodeConfig(), decoderProfile(), 'stale')).toMatchObject({
      hwaccel: 'cuda',
      hwaccelDevice: '0',
    })
  })

  it('builds rate-control select state and hints from encoder profile capabilities', () => {
    expect(buildRateControlViewState(encoderProfile(), 'cq')).toEqual({
      options: [
        { value: 'cq', label: 'CQ' },
        { value: 'bitrate', label: 'Bitrate' },
      ],
      disabled: false,
      modeHint: undefined,
      valueHint: '单位: CQ',
    })

    expect(buildRateControlViewState({ ...encoderProfile(), rateControlModes: [] }, 'cq')).toEqual({
      options: [],
      disabled: true,
      modeHint: '未探测到可用码率控制模式',
      valueHint: '未探测到可用码率控制模式',
    })
  })

  it('resolves rate-control mode selection and normalizes segment frame counts', () => {
    expect(resolveRateControlModeSelection(encoderProfile(), 'bitrate')).toEqual({
      mode: 'bitrate',
      value: 8000,
    })
    expect(resolveRateControlModeSelection(encoderProfile(), 'qp')).toBeNull()

    expect(normalizeSegmentFrames(12.6)).toBe(13)
    expect(normalizeSegmentFrames(0)).toBe(1000)
    expect(normalizeSegmentFrames(Number.NaN)).toBe(1000)
  })
})
