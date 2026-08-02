import { describe, expect, it } from 'vitest'

import {
  algorithmSupportsBackend,
  findInterpolationAlgorithm,
  findSuperResolutionAlgorithm,
  pickBackendSupportedAlgorithmName,
  pickSupportedBackend,
} from '@/services/preset/enhance-workflow-lookup'
import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/protocol'
import { createAlgorithmInfo, createEnvironmentResult } from '../../fixtures/environment'

const interpolation: AlgorithmInfo = createAlgorithmInfo({
  name: 'rife',
  family: 'rife',
  tensorBackends: ['pytorch', 'onnx'],
  models: ['4.25'],
  onnxModels: ['rife.onnx'],
  inputFrameMode: 'none',
})

const superResolution: AlgorithmInfo = createAlgorithmInfo({
  name: 'ppmsvsr',
  family: 'paddlegan_vsr',
  tensorBackends: ['paddle'],
  models: ['x4'],
  scaleFactors: [4],
  modelLicense: null,
  inputFrameMode: 'editable_chunk',
})

function env(): EnvironmentCheckResult {
  return createEnvironmentResult({
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: ['cuda'], paddle: ['cuda'], onnx: ['cuda'] },
    interpolationAlgorithms: [interpolation],
    superResolutionAlgorithms: [superResolution],
    runtimeMode: 'bundled',
  })
}

describe('enhance workflow lookup rules', () => {
  it('finds algorithms and selects a supported tensor backend without Vue state', () => {
    expect(findInterpolationAlgorithm(env(), 'rife')).toEqual(interpolation)
    expect(findSuperResolutionAlgorithm(env(), 'ppmsvsr')).toEqual(superResolution)
    expect(findInterpolationAlgorithm(null, 'rife')).toBeUndefined()

    expect(pickSupportedBackend(interpolation, 'onnx')).toBe('onnx')
    expect(pickSupportedBackend(superResolution, 'onnx')).toBe('paddle')
    expect(pickSupportedBackend(undefined, 'pytorch')).toBe('pytorch')
  })

  it('checks explicit backend support without falling back to another backend', () => {
    expect(algorithmSupportsBackend(interpolation, 'onnx')).toBe(true)
    expect(algorithmSupportsBackend(superResolution, 'onnx')).toBe(false)
    expect(algorithmSupportsBackend({ ...superResolution, tensorBackends: [] }, 'paddle')).toBe(false)
    expect(algorithmSupportsBackend(undefined, 'pytorch')).toBe(false)
  })

  it('picks a backend-supported algorithm name with first-item and hard-coded fallbacks', () => {
    expect(pickBackendSupportedAlgorithmName([interpolation, superResolution], 'paddle', 'rife')).toBe('ppmsvsr')
    expect(pickBackendSupportedAlgorithmName([superResolution], 'onnx', 'placeholder')).toBe('ppmsvsr')
    expect(pickBackendSupportedAlgorithmName([], 'onnx', 'placeholder')).toBe('placeholder')
    expect(pickBackendSupportedAlgorithmName(undefined, 'onnx', 'placeholder')).toBe('placeholder')
  })
})
