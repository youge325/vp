import { describe, expect, it } from 'vitest'

import {
  applyInterpolationEnabled,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from '@/services/preset/enhance-workflow'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(): EnvironmentCheckResult {
  return {
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
    backendDeviceSupport: { pytorch: [], paddle: [], onnx: [] },
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
    runtimeMode: 'bundled',
  }
}

describe('enhance workflow mutation rules', () => {
  it('keeps interpolation on ONNX when Paddle super-resolution is enabled', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'pytorch'
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'

    applySuperResolutionEnabled(workflow, true, makeEnv())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
  })

  it('clamps fixed PaddleGAN scale and frame window edits', () => {
    const env = makeEnv()
    const workflow = createDefaultWorkflowConfigForEnvironment(null)

    workflow.superResolution.algorithm = 'edvr'
    applySuperResolutionScale(workflow, 2, env)
    applySuperResolutionNumFrames(workflow, 3, env)

    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.numFrames).toBe(5)
  })

  it('keeps simple toggles as workflow-only mutations', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)

    applyInterpolationEnabled(workflow, false, makeEnv())
    applySuperResolutionEnabled(workflow, false, makeEnv())

    expect(workflow.interpolation.enabled).toBe(false)
    expect(workflow.superResolution.enabled).toBe(false)
  })
})
