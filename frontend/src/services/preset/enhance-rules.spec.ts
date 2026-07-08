import { describe, expect, it } from 'vitest'

import {
  applySuperResolutionAlgorithmDefaults,
  fixedRuntimeFrameCount,
  isPaddleGanVsrAlgorithm,
  pickDefaultInterpolationAlgorithm,
  pickDefaultSuperResolutionAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-rules'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import { createDefaultWorkflowConfig } from './defaults'

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

describe('algorithm capability metadata helpers', () => {
  it('classifies PaddleGAN VSR from metadata rather than a hard-coded name list', () => {
    const algorithm = {
      name: 'custom-vsr',
      family: 'paddlegan_vsr',
      tensorBackends: ['paddle'],
      models: ['x4'],
      fixedScaleFactor: 4,
      inputFrameMode: 'editable_chunk',
    }

    expect(isPaddleGanVsrAlgorithm(algorithm)).toBe(true)
    expect(superResolutionInputFrameMode(algorithm)).toBe('editable_chunk')
  })

  it('resolves fixed-window runtime frame counts from model metrics first', () => {
    const algorithm = {
      name: 'custom-window-vsr',
      family: 'paddlegan_vsr',
      tensorBackends: ['paddle'],
      models: ['x4'],
      defaultNumFrames: 7,
      inputFrameMode: 'fixed_window',
      modelDetails: [
        {
          name: 'x4',
          label: 'Custom',
          metrics: {
            runtimeFrameCount: 5,
            analysisStatus: 'ok',
            analysisNotes: [],
          },
        },
      ],
    }

    expect(fixedRuntimeFrameCount(algorithm)).toBe(5)
    expect(superResolutionInputFrameMode(algorithm)).toBe('fixed_window')
  })

  it('applies PaddleGAN defaults through the shared workflow strategy', () => {
    const workflow = createDefaultWorkflowConfig()
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.numFrames = 3
    workflow.superResolution.onnxModel = 'stale.onnx'

    applySuperResolutionAlgorithmDefaults(
      workflow,
      {
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        fixedScaleFactor: 4,
        defaultNumFrames: 8,
        inputFrameMode: 'editable_chunk',
      },
      null,
    )

    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.onnxModel).toBe('')
    expect(workflow.superResolution.numFrames).toBe(8)
  })
})
