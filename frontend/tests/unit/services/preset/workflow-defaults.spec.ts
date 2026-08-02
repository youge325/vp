import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function makeEnv(
  overrides: Parameters<typeof createEnvironmentResult>[0] = {},
): EnvironmentCheckResult {
  return createEnvironmentResult(overrides)
}

describe('workflow defaults', () => {
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
      algorithm: 'real-rawvsr-basicvsr',
      onnxModel: '',
      tensorBackend: 'pytorch',
      engine: 'cuda',
      numFrames: 10,
    })
  })

  it('hydrates default algorithms, models, and ONNX models from environment', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      interpolationAlgorithms: [
        { name: 'slow-rife', tensorBackends: ['onnx'], models: ['onnx-only'], onnxModels: ['slow.onnx'] },
        { name: 'rife-fast', tensorBackends: ['pytorch', 'onnx'], models: ['4.26'], onnxModels: ['fast.onnx'] },
      ],
      superResolutionAlgorithms: [
        { name: 'realesrgan-x4', tensorBackends: ['onnx'], models: [], onnxModels: ['sr-x4.onnx'] },
      ],
    }))

    expect(workflow.interpolation.algorithm).toBe('rife-fast')
    expect(workflow.interpolation.model).toBe('4.26')
    expect(workflow.interpolation.onnxModel).toBe('fast.onnx')
    expect(workflow.superResolution.algorithm).toBe('realesrgan-x4')
    expect(workflow.superResolution.onnxModel).toBe('sr-x4.onnx')
    expect(workflow.superResolution.scaleFactor).toBe(2)
  })

  it('applies existing initial engine preference for NVIDIA and Hygon environments', () => {
    const nvidiaWorkflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      gpu: {
        adapters: [{ name: 'RTX', vendor: 'nvidia' }],
      },
      tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: [], onnx: ['cuda', 'tensorrt'] },
    }))
    const hygonWorkflow = createDefaultWorkflowConfigForEnvironment(makeEnv({
      gpu: {
        adapters: [{ name: 'DCU', vendor: 'hygon' }],
      },
      tensorEngines: { pytorch: ['cuda', 'dcu'], paddle: [], onnx: ['cuda'] },
    }))

    expect(nvidiaWorkflow.interpolation.engine).toBe('tensorrt')
    expect(nvidiaWorkflow.superResolution.engine).toBe('cuda')
    expect(hygonWorkflow.interpolation.engine).toBe('dcu')
    expect(hygonWorkflow.superResolution.engine).toBe('cuda')
  })
})
