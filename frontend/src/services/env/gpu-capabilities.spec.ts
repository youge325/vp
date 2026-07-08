import { describe, expect, it } from 'vitest'

import * as gpuCapabilities from './gpu-capabilities'
import { getAvailableEngines, getVisibleBackends, shouldShowEngineSelector } from './gpu-capabilities'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function env(overrides: Partial<EnvironmentCheckResult>): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: { hwaccels: [], encoderProfiles: [], decoderProfiles: [] },
    gpu: { available: false, devices: [], adapters: [] },
    tensorBackends: {},
    tensorEngines: {},
    rifeModel: {},
    ...overrides,
  }
}

describe('GPU capabilities', () => {
  it('keeps legacy vendor and support helpers out of the public surface', () => {
    expect('inferGpuVendor' in gpuCapabilities).toBe(false)
    expect('getBackendDeviceSupport' in gpuCapabilities).toBe(false)
  })

  it('returns all backends when no adapter-specific support is available', () => {
    expect(getVisibleBackends(null)).toEqual(['pytorch', 'paddle', 'onnx'])
    expect(getVisibleBackends(env({ gpu: { available: true, devices: [], adapters: [] } }))).toEqual([
      'pytorch',
      'paddle',
      'onnx',
    ])
  })

  it('filters visible backends by adapter vendor support metadata', () => {
    const result = env({
      gpu: { available: true, devices: [], adapters: [{ name: 'DCU', vendor: 'hygon', deviceType: 'discrete' }] },
      backendDeviceSupport: {
        pytorch: ['nvidia'],
        paddle: ['hygon'],
        onnx: ['nvidia'],
      },
    })

    expect(getVisibleBackends(result)).toEqual(['paddle'])
  })

  it('uses explicit tensor engine metadata before GPU fallback heuristics', () => {
    const result = env({
      gpu: { available: true, devices: ['NVIDIA GPU'], adapters: [], cudaAvailable: true },
      tensorEngines: { pytorch: ['cuda'] },
    })

    expect(getAvailableEngines(result, 'pytorch')).toEqual(['cuda'])
    expect(shouldShowEngineSelector(result, 'pytorch')).toBe(true)
  })
})
