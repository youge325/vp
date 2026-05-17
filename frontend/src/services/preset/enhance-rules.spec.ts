import { describe, expect, it } from 'vitest'

import {
  pickDefaultInterpolationAlgorithm,
  pickDefaultSuperResolutionAlgorithm,
} from './enhance-rules'
import type { EnvironmentCheckResult } from '@/types/domain/env'

// Phase 8 — 算法默认值挑选必须按当前 tensorBackend 过滤。
// 如果不过滤,Paddle backend 下会默认到 RIFE(PyTorch only),
// 用户点开预设就看到自相矛盾的状态。

function makeEnv(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: false, devices: [], adapters: [] },
    tensorBackends: {},
    tensorEngines: {},
    onnxRuntime: { available: false, providers: [] },
    rifeModel: { available: false },
    ...overrides,
  } as EnvironmentCheckResult
}

describe('pickDefaultInterpolationAlgorithm (Phase 8 backend-aware)', () => {
  it('returns RIFE under pytorch backend when RIFE declares pytorch support', () => {
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
      ],
    })
    expect(pickDefaultInterpolationAlgorithm(env, 'pytorch')).toBe('rife')
  })

  it('returns RIFE under onnx backend when RIFE declares onnx support', () => {
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
      ],
    })
    expect(pickDefaultInterpolationAlgorithm(env, 'onnx')).toBe('rife')
  })

  it('falls back to the first registered algorithm when nothing supports the requested backend', () => {
    // RIFE only lists pytorch/onnx; asking for paddle falls back to first
    // registered algorithm. UI will then filter that algorithm out via
    // the same ``tensorBackends.includes`` check in useEnhanceForm,
    // so the dropdown is correctly empty — the fallback only serves to
    // avoid an undefined ``workflow.interpolation.algorithm`` slot.
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
      ],
    })
    expect(pickDefaultInterpolationAlgorithm(env, 'paddle')).toBe('rife')
  })

  it('prefers a backend-compatible entry over an incompatible one', () => {
    const env = makeEnv({
      interpolationAlgorithms: [
        { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'] },
        { name: 'paddle-rife', tensorBackends: ['paddle'], models: ['v1'] },
      ],
    })
    expect(pickDefaultInterpolationAlgorithm(env, 'paddle')).toBe('paddle-rife')
    expect(pickDefaultInterpolationAlgorithm(env, 'pytorch')).toBe('rife')
  })

  it('returns hard-coded rife when checkResult is null', () => {
    expect(pickDefaultInterpolationAlgorithm(null, 'pytorch')).toBe('rife')
  })
})

describe('pickDefaultSuperResolutionAlgorithm (Phase 8 backend-aware)', () => {
  it('returns the first algorithm that declares the requested backend', () => {
    const env = makeEnv({
      superResolutionAlgorithms: [
        { name: 'placeholder', tensorBackends: ['onnx'], models: [] },
        { name: 'realesrgan-plan', tensorBackends: ['onnx'], models: [] },
      ],
    })
    expect(pickDefaultSuperResolutionAlgorithm(env, 'onnx')).toBe('placeholder')
  })

  it('falls back to the first registered entry when no algorithm matches the backend', () => {
    const env = makeEnv({
      superResolutionAlgorithms: [
        { name: 'placeholder', tensorBackends: ['onnx'], models: [] },
      ],
    })
    // pytorch backend asked but only onnx-tagged algorithms exist
    expect(pickDefaultSuperResolutionAlgorithm(env, 'pytorch')).toBe('placeholder')
  })

  it('returns hard-coded placeholder when checkResult is null', () => {
    expect(pickDefaultSuperResolutionAlgorithm(null, 'onnx')).toBe('placeholder')
  })
})
