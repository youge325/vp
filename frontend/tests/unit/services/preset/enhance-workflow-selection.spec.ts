import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import {
  applyInterpolationBackendSelectionDefaults,
  applySuperResolutionAlgorithmSelectionDefaults,
  preferOnnxInterpolationForPaddleSuperResolution,
  resolveSuperResolutionNumFrames,
  resolveSuperResolutionScale,
} from '@/services/preset/enhance-workflow-selection'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(): EnvironmentCheckResult {
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
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda'], onnx: ['cuda', 'tensorrt'] },
    onnxRuntime: { available: true, providers: ['CUDAExecutionProvider'] },
    rifeModel: { available: true, version: '4.25' },
    interpolationAlgorithms: [
      { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
      { name: 'rife-lite', tensorBackends: ['pytorch'], models: ['lite'], onnxModels: [] },
      { name: 'onnx-only', tensorBackends: ['onnx'], models: ['onnx'], onnxModels: ['onnx-only.onnx'] },
    ],
    superResolutionAlgorithms: [
      { name: 'placeholder', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'], scaleFactors: [2] },
      {
        name: 'ppmsvsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        inputFrameMode: 'editable_chunk',
        defaultNumFrames: 10,
      },
      {
        name: 'edvr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        inputFrameMode: 'fixed_window',
        defaultNumFrames: 5,
      },
    ],
    animeProfiles: ['clean-lines'],
  }
}

describe('enhance workflow selection rules', () => {
  it('repairs interpolation algorithm/model and ONNX model when backend changes', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.algorithm = 'rife-lite'
    workflow.interpolation.model = 'lite'
    workflow.interpolation.onnxModel = ''

    applyInterpolationBackendSelectionDefaults(workflow, 'onnx', makeEnv())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.engine).toBe('cuda')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
  })

  it('moves pytorch interpolation to ONNX when Paddle super-resolution is active', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'pytorch'
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'

    preferOnnxInterpolationForPaddleSuperResolution(workflow, makeEnv())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
  })

  it('applies supported backend and fixed PaddleGAN value rules', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.numFrames = 3
    workflow.superResolution.onnxModel = 'stale.onnx'

    applySuperResolutionAlgorithmSelectionDefaults(workflow, 'edvr', makeEnv())

    expect(workflow.superResolution.algorithm).toBe('edvr')
    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.engine).toBe('cuda')
    expect(workflow.superResolution.onnxModel).toBe('')
    expect(resolveSuperResolutionScale(workflow, 2, makeEnv())).toBe(4)
    expect(resolveSuperResolutionNumFrames(workflow, 3, makeEnv())).toBe(5)
  })
})
