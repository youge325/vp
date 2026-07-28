import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import {
  applyInterpolationBackendSelectionDefaults,
  applySuperResolutionAlgorithmSelectionDefaults,
  preferOnnxInterpolationForPaddleSuperResolution,
  resolveSuperResolutionNumFrames,
  resolveSuperResolutionScale,
} from '@/services/preset/enhance-workflow-selection'
import { createEnhanceEnvironment } from '../../fixtures/environment'

describe('enhance workflow selection rules', () => {
  it('repairs interpolation algorithm/model and ONNX model when backend changes', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.algorithm = 'rife-lite'
    workflow.interpolation.model = 'lite'
    workflow.interpolation.onnxModel = ''

    applyInterpolationBackendSelectionDefaults(workflow, 'onnx', createEnhanceEnvironment())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.engine).toBe('cuda')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife_v4.25.onnx')
  })

  it('moves pytorch interpolation to ONNX when Paddle super-resolution is active', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'pytorch'
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'

    preferOnnxInterpolationForPaddleSuperResolution(workflow, createEnhanceEnvironment())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife_v4.25.onnx')
  })

  it('applies supported backend and fixed PaddleGAN value rules', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.numFrames = 3
    workflow.superResolution.onnxModel = 'stale.onnx'

    const environment = createEnhanceEnvironment()
    applySuperResolutionAlgorithmSelectionDefaults(workflow, 'edvr', environment)

    expect(workflow.superResolution.algorithm).toBe('edvr')
    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.engine).toBe('cuda')
    expect(workflow.superResolution.onnxModel).toBe('')
    expect(resolveSuperResolutionScale(workflow, 2, environment)).toBe(4)
    expect(resolveSuperResolutionNumFrames(workflow, 3, environment)).toBe(5)
  })
})
