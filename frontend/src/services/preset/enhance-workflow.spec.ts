import { describe, expect, it } from 'vitest'

import {
  applyInterpolationAlgorithmSelection,
  applyInterpolationBackendSelection,
  applyInterpolationEnabled,
  applySuperResolutionAlgorithmSelection,
  applySuperResolutionBackendSelection,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from './enhance-workflow'
import {
  applyInterpolationAlgorithmSelectionDefaults,
  applyInterpolationBackendSelectionDefaults,
  applySuperResolutionAlgorithmSelectionDefaults,
  applySuperResolutionBackendSelectionDefaults,
} from './enhance-workflow-selection'
import { createDefaultWorkflowConfigForEnvironment } from './workflow-defaults'
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
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
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

describe('enhance workflow mutation rules', () => {
  it('exposes selection implementations without pass-through wrappers', () => {
    expect(applyInterpolationBackendSelection).toBe(applyInterpolationBackendSelectionDefaults)
    expect(applySuperResolutionBackendSelection).toBe(applySuperResolutionBackendSelectionDefaults)
    expect(applyInterpolationAlgorithmSelection).toBe(applyInterpolationAlgorithmSelectionDefaults)
    expect(applySuperResolutionAlgorithmSelection).toBe(applySuperResolutionAlgorithmSelectionDefaults)
  })

  it('switches interpolation backend and repairs unsupported algorithm/model defaults', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.algorithm = 'rife-lite'
    workflow.interpolation.model = 'lite'
    workflow.interpolation.onnxModel = ''

    applyInterpolationBackendSelection(workflow, 'onnx', makeEnv())

    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.engine).toBe('cuda')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.model).toBe('4.25')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
  })

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

  it('applies PaddleGAN algorithm defaults through algorithm selection', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.tensorBackend = 'onnx'
    workflow.superResolution.scaleFactor = 2
    workflow.superResolution.numFrames = 3
    workflow.superResolution.onnxModel = 'stale.onnx'

    applySuperResolutionAlgorithmSelection(workflow, 'ppmsvsr', makeEnv())

    expect(workflow.superResolution.algorithm).toBe('ppmsvsr')
    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.numFrames).toBe(10)
    expect(workflow.superResolution.onnxModel).toBe('')
  })

  it('clamps fixed PaddleGAN scale and frame window edits', () => {
    const env = makeEnv()
    const workflow = createDefaultWorkflowConfigForEnvironment(null)

    applySuperResolutionAlgorithmSelection(workflow, 'edvr', env)
    applySuperResolutionScale(workflow, 2, env)
    applySuperResolutionNumFrames(workflow, 3, env)

    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(workflow.superResolution.numFrames).toBe(5)
  })

  it('keeps simple toggles as workflow-only mutations', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)

    applyInterpolationEnabled(workflow, false, makeEnv())
    applySuperResolutionEnabled(workflow, false, makeEnv())
    applyInterpolationAlgorithmSelection(workflow, 'rife-lite', makeEnv())
    applySuperResolutionBackendSelection(workflow, 'onnx', makeEnv())

    expect(workflow.interpolation.enabled).toBe(false)
    expect(workflow.interpolation.algorithm).toBe('rife-lite')
    expect(workflow.interpolation.model).toBe('lite')
    expect(workflow.superResolution.enabled).toBe(false)
    expect(workflow.superResolution.tensorBackend).toBe('onnx')
    expect(workflow.superResolution.algorithm).toBe('placeholder')
  })
})
