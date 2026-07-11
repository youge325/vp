import { describe, expect, it } from 'vitest'

import * as workflowDefaults from '@/services/preset/workflow-defaults'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(overrides: Partial<EnvironmentCheckResult> = {}): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: true, devices: ['GPU'], adapters: [] },
    tensorBackends: { pytorch: true, paddle: true, onnx: true },
    tensorEngines: {},
    onnxRuntime: { available: false, providers: [] },
    rifeModel: { available: false },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    animeProfiles: [],
    ...overrides,
  } as EnvironmentCheckResult
}

describe('workflow defaults', () => {
  it('keeps the base workflow factory private', () => {
    expect('createDefaultWorkflowConfig' in workflowDefaults).toBe(false)
  })

  it('keeps environment hydration private to the environment-aware factory', () => {
    expect('applyEnvironmentWorkflowDefaults' in workflowDefaults).toBe(false)
  })

  it('creates fallback workflow defaults without environment metadata', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)

    expect(workflow.interpolation).toMatchObject({
      enabled: true,
      targetFps: 60,
      multi: 2,
      algorithm: 'rife',
      model: '4.25',
      onnxModel: '',
      tensorBackend: 'pytorch',
      engine: 'cuda',
    })
    expect(workflow.superResolution).toMatchObject({
      enabled: false,
      scaleFactor: 2,
      algorithm: 'placeholder',
      onnxModel: '',
      tensorBackend: 'onnx',
      engine: 'cuda',
      numFrames: 10,
      autoDownloadWeights: false,
    })
    expect(workflow.anime.profile).toBe('clean-lines')
  })

  it('hydrates default algorithms, models, ONNX models, and anime profile from environment', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      interpolationAlgorithms: [
        { name: 'slow-rife', tensorBackends: ['onnx'], models: ['onnx-only'], onnxModels: ['slow.onnx'] },
        { name: 'rife-fast', tensorBackends: ['pytorch', 'onnx'], models: ['4.26'], onnxModels: ['fast.onnx'] },
      ],
      superResolutionAlgorithms: [
        { name: 'realesrgan-x4', tensorBackends: ['onnx'], models: [], onnxModels: ['sr-x4.onnx'], scaleFactors: [4] },
      ],
      animeProfiles: ['line-art'],
    }))

    expect(workflow.interpolation.algorithm).toBe('rife-fast')
    expect(workflow.interpolation.model).toBe('4.26')
    expect(workflow.interpolation.onnxModel).toBe('fast.onnx')
    expect(workflow.superResolution.algorithm).toBe('realesrgan-x4')
    expect(workflow.superResolution.onnxModel).toBe('sr-x4.onnx')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.anime.profile).toBe('line-art')
  })

  it('applies existing initial engine preference for NVIDIA and Hygon environments', () => {
    const nvidiaWorkflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      gpu: {
        available: true,
        devices: ['NVIDIA GPU'],
        adapters: [{ name: 'RTX', vendor: 'nvidia', deviceType: 'discrete' }],
      },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
    }))
    const hygonWorkflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      gpu: {
        available: true,
        devices: ['Hygon GPU'],
        adapters: [{ name: 'DCU', vendor: 'hygon', deviceType: 'discrete' }],
      },
      tensorEngines: { pytorch: ['cuda', 'dcu'], onnx: ['cuda'] },
    }))

    expect(nvidiaWorkflow.interpolation.engine).toBe('tensorrt')
    expect(nvidiaWorkflow.superResolution.engine).toBe('cuda')
    expect(hygonWorkflow.interpolation.engine).toBe('dcu')
    expect(hygonWorkflow.superResolution.engine).toBe('cuda')
  })
})
