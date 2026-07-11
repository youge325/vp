import { describe, expect, it } from 'vitest'

import * as gpuCapabilities from '@/services/env/gpu-capabilities'
import { getAvailableEngines, getVisibleBackends, shouldShowEngineSelector } from '@/services/env/gpu-capabilities'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function env(overrides: Partial<EnvironmentCheckResult>): EnvironmentCheckResult {
  return {
    ffmpeg: { available: true, hwaccels: [], encoderProfiles: [], decoderProfiles: [] },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: [], paddle: [], onnx: [] },
    backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    runtimeMode: 'external',
    ...overrides,
  }
}

describe('GPU capabilities', () => {
  it('keeps legacy vendor and support helpers out of the public surface', () => {
    expect('inferGpuVendor' in gpuCapabilities).toBe(false)
    expect('getBackendDeviceSupport' in gpuCapabilities).toBe(false)
  })

  it('shows no checked backend without explicit engine metadata', () => {
    expect(getVisibleBackends(null)).toEqual(['pytorch', 'paddle', 'onnx'])
    expect(getVisibleBackends(env({}))).toEqual([])
  })

  it('filters visible backends by adapter vendor support metadata', () => {
    const result = env({
      gpu: { adapters: [{ name: 'DCU', vendor: 'hygon', deviceType: 'discrete' }] },
      tensorEngines: { pytorch: ['cuda'], paddle: ['dcu'], onnx: ['cuda'] },
      backendDeviceSupport: {
        pytorch: ['nvidia'],
        paddle: ['hygon'],
        onnx: ['nvidia'],
      },
    })

    expect(getVisibleBackends(result)).toEqual(['paddle'])
  })

  it('uses only explicit tensor engine metadata', () => {
    const result = env({
      gpu: { adapters: [{ name: 'NVIDIA GPU', vendor: 'nvidia', deviceType: 'discrete' }] },
      tensorEngines: { pytorch: ['cuda'], paddle: [], onnx: [] },
    })

    expect(getAvailableEngines(result, 'pytorch')).toEqual(['cuda'])
    expect(shouldShowEngineSelector(result, 'pytorch')).toBe(true)
  })
})
