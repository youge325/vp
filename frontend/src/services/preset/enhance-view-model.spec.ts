import { describe, expect, it } from 'vitest'

import { buildEnhanceViewModel } from './enhance-view-model'
import { createDefaultWorkflowConfig } from './workflow-defaults'
import type { AlgorithmInfo } from '@/types/domain/env'

const rife: AlgorithmInfo = {
  name: 'rife',
  tensorBackends: ['pytorch', 'onnx'],
  models: ['4.25'],
  onnxModels: ['rife_v4.25.onnx'],
  modelDetails: [
    {
      name: '4.25',
      label: 'RIFE 4.25',
      metrics: {
        parameterCount: 5670892,
        parameterBytes: 22683568,
        gflopsPerMegapixel: 18.5,
        activationBytesPerMegapixel: 694800000,
        runtimeOverheadBytes: 38000000,
        inputModulo: 64,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    },
  ],
  onnxModelDetails: [
    {
      name: 'rife_v4.25.onnx',
      label: 'rife_v4.25.onnx',
      metrics: {
        parameterCount: 5670892,
        parameterBytes: 22683568,
        gflopsPerMegapixel: 18.5,
        activationBytesPerMegapixel: 694800000,
        runtimeOverheadBytes: 38000000,
        inputModulo: 64,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    },
  ],
}

const ppmsvsr: AlgorithmInfo = {
  name: 'ppmsvsr',
  family: 'paddlegan_vsr',
  tensorBackends: ['paddle'],
  models: ['x4'],
  scaleFactors: [4],
  fixedScaleFactor: 4,
  inputFrameMode: 'editable_chunk',
  defaultNumFrames: 10,
  modelDetails: [
    {
      name: 'x4',
      label: 'PP-MSVSR',
      metrics: {
        parameterCount: 1453607,
        parameterBytes: 5814428,
        gflopsPerMegapixel: 120,
        activationBytesPerMegapixel: 1981031424,
        runtimeOverheadBytes: 2391117604,
        runtimeFrameCount: null,
        inputModulo: 4,
        analysisStatus: 'ok',
        analysisNotes: [],
        engineMetrics: {
          tensorrt: {
            gflopsPerMegapixel: 120,
            activationBytesPerMegapixel: 3688504346,
            runtimeOverheadBytes: 0,
            runtimeFrameCount: null,
            analysisStatus: 'ok',
            analysisNotes: ['TensorRT calibrated'],
          },
        },
      },
    },
  ],
}

const edvr: AlgorithmInfo = {
  name: 'edvr',
  family: 'paddlegan_vsr',
  tensorBackends: ['paddle'],
  models: ['x4'],
  scaleFactors: [4],
  fixedScaleFactor: 4,
  inputFrameMode: 'fixed_window',
  defaultNumFrames: 5,
  modelDetails: [
    {
      name: 'x4',
      label: 'EDVR',
      metrics: {
        parameterCount: 20633827,
        parameterBytes: 82535308,
        gflopsPerMegapixel: 240,
        activationBytesPerMegapixel: 1000,
        runtimeOverheadBytes: 100,
        runtimeFrameCount: 5,
        inputModulo: 4,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    },
  ],
}

describe('enhance view-model rules', () => {
  it('resolves selected models and estimates SR-to-interpolation runtime rows', () => {
    const workflow = createDefaultWorkflowConfig()
    workflow.processOrder = 'super_resolution_then_interpolation'
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'pytorch'
    workflow.interpolation.engine = 'cuda'
    workflow.interpolation.algorithm = 'rife'
    workflow.interpolation.model = '4.25'
    workflow.interpolation.fp16 = false
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'cuda'
    workflow.superResolution.algorithm = 'ppmsvsr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.currentInterpolationModelDetail?.name).toBe('4.25')
    expect(model.currentSuperResolutionModelDetail?.name).toBe('x4')
    expect(model.interpolationInputDimensions).toEqual({ width: 2560, height: 1152 })
    expect(model.interpolationRuntimeEstimate?.effectiveHeight).toBe(1152)
    expect(model.interpolationMetricRows[2].value).toBe('1.96 GiB')
    expect(model.superResolutionMetricRows[2].value).toBe('5.63 GiB')
    expect(model.combinedVramMetricRows[0].value).toBe('5.63 GiB')
    expect(model.effectiveSuperResolutionNumFrames).toBe(10)
  })

  it('uses fixed-window SR runtime frames instead of stale editable workflow value', () => {
    const workflow = createDefaultWorkflowConfig()
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'cuda'
    workflow.superResolution.algorithm = 'edvr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: edvr,
    })

    expect(model.isPaddleGanSuperResolution).toBe(true)
    expect(model.isSuperResolutionInputFramesEditable).toBe(false)
    expect(model.superResolutionFixedWindowRows).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
    expect(model.superResolutionRuntimeEstimate?.vramBytes).toBe(
      buildEnhanceViewModel({
        workflow: {
          ...workflow,
          superResolution: { ...workflow.superResolution, numFrames: 2 },
        },
        activeVideoDimensions: { width: 640, height: 288 },
        currentInterpolationAlgorithm: rife,
        currentSuperResolutionAlgorithm: edvr,
      }).superResolutionRuntimeEstimate?.vramBytes,
    )
    expect(model.effectiveSuperResolutionNumFrames).toBe(5)
  })

  it('uses selected TensorRT engine metrics for super-resolution estimates', () => {
    const workflow = createDefaultWorkflowConfig()
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'tensorrt'
    workflow.superResolution.algorithm = 'ppmsvsr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 5

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.currentSuperResolutionRuntimeDetail?.metrics.analysisNotes).toEqual(['TensorRT calibrated'])
    expect(model.superResolutionMetricRows[1].value).toBe('22.1 GFLOPs')
    expect(model.superResolutionMetricRows[2].value).toBe('3.17 GiB')
  })
})
