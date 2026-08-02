import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { applySuperResolutionAlgorithmDefaults } from '@/services/preset/enhance-super-resolution-defaults'
import {
  createAlgorithmInfo,
  createEnvironmentResult,
} from '../../fixtures/environment'

describe('super-resolution algorithm defaults', () => {
  it('applies PaddleGAN VSR fixed backend, scale, ONNX, and frame defaults', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.numFrames = 3
    workflow.superResolution.onnxModel = 'stale.onnx'

    applySuperResolutionAlgorithmDefaults(
      workflow,
      createAlgorithmInfo({
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        modelLicense: null,
        defaultNumFrames: 8,
        inputFrameMode: 'editable_chunk',
      }),
      null,
    )

    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.onnxModel).toBe('')
    expect(workflow.superResolution.numFrames).toBe(8)
  })

  it('preserves configured scale and repairs the ONNX model for non-Paddle algorithms', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.algorithm = 'sr'
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.onnxModel = ''
    const env = createEnvironmentResult({
      superResolutionAlgorithms: [
        {
          name: 'sr',
          tensorBackends: ['onnx'],
          models: [],
          onnxModels: ['sr-x4.onnx'],
        },
      ],
    })

    applySuperResolutionAlgorithmDefaults(workflow, env.superResolutionAlgorithms?.[0], env)

    expect(workflow.superResolution.scaleFactor).toBe(2)
    expect(workflow.superResolution.onnxModel).toBe('sr-x4.onnx')
  })

  it('applies PyTorch CUDA defaults while preserving a supported BasicVSR scale', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.engine = 'tensorrt'
    workflow.superResolution.scaleFactor = 3

    applySuperResolutionAlgorithmDefaults(
      workflow,
      createAlgorithmInfo({
        name: 'real-rawvsr-basicvsr',
        family: 'pytorch_vsr',
        tensorBackends: ['pytorch'],
        scaleFactors: [2, 3, 4],
        defaultNumFrames: 10,
        inputFrameMode: 'editable_chunk',
      }),
      null,
    )

    expect(workflow.superResolution.tensorBackend).toBe('pytorch')
    expect(workflow.superResolution.engine).toBe('cuda')
    expect(workflow.superResolution.scaleFactor).toBe(3)
    expect(workflow.superResolution.onnxModel).toBe('')
  })
})
