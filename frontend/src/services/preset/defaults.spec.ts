import { describe, expect, it } from 'vitest'

import { createDefaultDecodeConfig, createDefaultWorkflowConfig } from './defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { HardwareDeviceOptionSpec } from '@/types/domain/capability'

const makeEnv = (decoderProfiles: EnvironmentCheckResult['ffmpeg']['decoderProfiles']): EnvironmentCheckResult => ({
  type: 'check',
  ffmpeg: {
    available: true,
    hwaccels: ['cuda', 'qsv', 'd3d11va'],
    encoderProfiles: [],
    decoderProfiles,
  },
  gpu: { available: true, devices: ['GPU'], adapters: [] },
  tensorBackends: { pytorch: false, paddle: false, onnx: false },
  tensorEngines: {},
  onnxRuntime: { available: false, providers: [] },
  rifeModel: { available: false },
  interpolationAlgorithms: [],
  superResolutionAlgorithms: [],
  animeProfiles: [],
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
  pixelFormats: [],
  hardwareDevices,
  hardwareDeviceOptions,
  options: [],
})

describe('createDefaultWorkflowConfig PaddleGAN SR fields', () => {
  it('creates independent super-resolution runtime fields', () => {
    const workflow = createDefaultWorkflowConfig()

    expect(workflow.superResolution.tensorBackend).toBe('onnx')
    expect(workflow.superResolution.engine).toBe('cuda')
    expect(workflow.superResolution.numFrames).toBe(10)
    expect(workflow.superResolution.autoDownloadWeights).toBe(true)
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
