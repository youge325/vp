import { describe, expect, it } from 'vitest'

import { getAvailableEngines, getVisibleBackends, shouldShowEngineSelector } from '@/services/env/gpu-capabilities'
import { createEnvironmentResult as env } from '../../fixtures/environment'

describe('GPU capabilities', () => {
  it('shows no checked backend without explicit engine metadata', () => {
    expect(getVisibleBackends(null)).toEqual(['pytorch', 'paddle', 'onnx'])
    expect(getVisibleBackends(env({}))).toEqual([])
  })

  it('uses detected engines even when adapter vendor metadata disagrees', () => {
    const result = env({
      gpu: { adapters: [{ name: 'DCU', vendor: 'hygon' }] },
      tensorEngines: { pytorch: ['cuda'], paddle: ['dcu'], onnx: ['cuda'] },
    })

    expect(getVisibleBackends(result)).toEqual(['pytorch', 'paddle', 'onnx'])
  })

  it('uses only explicit tensor engine metadata', () => {
    const result = env({
      gpu: { adapters: [{ name: 'NVIDIA GPU', vendor: 'nvidia' }] },
      tensorEngines: { pytorch: ['cuda'], paddle: [], onnx: [] },
    })

    expect(getAvailableEngines(result, 'pytorch')).toEqual(['cuda'])
    expect(shouldShowEngineSelector(result, 'pytorch')).toBe(true)
  })
})
