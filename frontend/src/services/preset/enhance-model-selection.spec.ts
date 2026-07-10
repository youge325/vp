import { describe, expect, it } from 'vitest'

import { buildEnhanceModelSelection } from './enhance-model-selection'
import { createDefaultWorkflowConfigForEnvironment } from './workflow-defaults'
import type { AlgorithmInfo } from '@/types/domain/env'

const interpolationAlgorithm: AlgorithmInfo = {
  name: 'rife',
  tensorBackends: ['pytorch', 'onnx'],
  models: ['4.25'],
  onnxModels: ['rife.onnx'],
  modelDetails: [
    {
      name: '4.25',
      label: 'RIFE 4.25',
      metrics: {
        parameterCount: 10,
        parameterBytes: 40,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    },
  ],
  onnxModelDetails: [
    {
      name: 'rife.onnx',
      label: 'RIFE ONNX',
      metrics: {
        parameterCount: 20,
        parameterBytes: 80,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    },
  ],
}

const superResolutionAlgorithm: AlgorithmInfo = {
  name: 'ppmsvsr',
  tensorBackends: ['paddle'],
  models: ['x4'],
  modelDetails: [
    {
      name: 'x4',
      label: 'PP-MSVSR',
      metrics: {
        parameterCount: 30,
        parameterBytes: 120,
        runtimeFrameCount: 5,
        analysisStatus: 'ok',
        analysisNotes: [],
        engineMetrics: {
          tensorrt: {
            parameterCount: 31,
            parameterBytes: 124,
            runtimeFrameCount: 7,
            analysisStatus: 'ok',
            analysisNotes: ['TensorRT override'],
          },
        },
      },
    },
  ],
}

describe('enhance model selection', () => {
  it('selects model lists, current model details, and engine runtime details', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.tensorBackend = 'onnx'
    workflow.interpolation.onnxModel = 'rife.onnx'
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'tensorrt'

    const selection = buildEnhanceModelSelection({
      workflow,
      currentInterpolationAlgorithm: interpolationAlgorithm,
      currentSuperResolutionAlgorithm: superResolutionAlgorithm,
    })

    expect(selection.interpolationModelDetails).toHaveLength(1)
    expect(selection.interpolationOnnxModelDetails).toHaveLength(1)
    expect(selection.currentInterpolationModelDetail?.name).toBe('rife.onnx')
    expect(selection.currentInterpolationRuntimeDetail?.label).toBe('RIFE ONNX')
    expect(selection.currentSuperResolutionModelDetail?.name).toBe('x4')
    expect(selection.currentSuperResolutionRuntimeDetail?.metrics.analysisNotes).toEqual(['TensorRT override'])
    expect(selection.superResolutionRuntimeFrameCount).toBe(7)
  })
})
