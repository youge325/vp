import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { applySuperResolutionAlgorithmDefaults } from '@/services/preset/enhance-super-resolution-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

describe('super-resolution algorithm defaults', () => {
  it('applies PaddleGAN VSR fixed backend, scale, ONNX, and frame defaults', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
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

  it('repairs unsupported scale and ONNX model for non-Paddle super-resolution algorithms', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.algorithm = 'sr'
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.onnxModel = ''
    const env = {
      superResolutionAlgorithms: [
        {
          name: 'sr',
          tensorBackends: ['onnx'],
          models: [],
          onnxModels: ['sr-x4.onnx'],
          scaleFactors: [4],
        },
      ],
    } as EnvironmentCheckResult

    applySuperResolutionAlgorithmDefaults(workflow, env.superResolutionAlgorithms?.[0], env)

    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.onnxModel).toBe('sr-x4.onnx')
  })
})
