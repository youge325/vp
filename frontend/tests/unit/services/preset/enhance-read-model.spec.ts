import { describe, expect, it } from 'vitest'

import { buildEnhanceReadModel } from '@/services/preset/enhance-read-model'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { AlgorithmInfo } from '@/types/protocol'
import {
  createAlgorithmInfo,
  createEdvrAlgorithm,
  createModelVariantInfo,
  createPpmsvsrAlgorithm,
  createRealRawVsrBasicVsrAlgorithm,
  createRifeAlgorithm,
} from '../../fixtures/environment'

const rife: AlgorithmInfo = createRifeAlgorithm()
const ppmsvsr: AlgorithmInfo = createPpmsvsrAlgorithm()
const edvr: AlgorithmInfo = createEdvrAlgorithm()

describe('enhance view-model rules', () => {
  it('uses the selected ONNX detail instead of the native model mirror', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'onnx'
    workflow.interpolation.onnxModel = 'rife.onnx'
    const algorithm = createAlgorithmInfo({
      name: 'rife',
      tensorBackends: ['pytorch', 'onnx'],
      models: ['native'],
      onnxModels: ['rife.onnx'],
      modelDetails: [
        createModelVariantInfo({
          name: 'native',
          metrics: { parameterCount: 10 },
        }),
      ],
      onnxModelDetails: [
        createModelVariantInfo({
          name: 'rife.onnx',
          metrics: { parameterCount: 20 },
        }),
      ],
    })

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: algorithm,
      currentSuperResolutionAlgorithm: undefined,
    })

    expect(model.interpolationMetricRows[0].value).toBe('20')
  })

  it('resolves selected models and estimates SR-to-interpolation runtime rows', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
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

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.interpolationMetricRows[2].value).toBe('1.96 GiB')
    expect(model.superResolutionMetricRows[2].value).toBe('5.63 GiB')
    expect(model.combinedVramMetricRows[0].value).toBe('5.63 GiB')
    expect(model.effectiveSuperResolutionNumFrames).toBe(10)
  })

  it('uses fixed-window SR runtime frames instead of stale editable workflow value', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'cuda'
    workflow.superResolution.algorithm = 'edvr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: edvr,
    })

    expect(model.isSuperResolutionInputFramesEditable).toBe(false)
    expect(model.superResolutionFixedWindowRows).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
    expect(model.superResolutionMetricRows).toEqual(buildEnhanceReadModel({
      workflow: {
        ...workflow,
        superResolution: { ...workflow.superResolution, numFrames: 2 },
      },
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: edvr,
    }).superResolutionMetricRows)
    expect(model.effectiveSuperResolutionNumFrames).toBe(5)
  })

  it('selects BasicVSR metrics and license metadata for the active scale', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.enabled = true
    workflow.superResolution.scaleFactor = 3
    const algorithm = createRealRawVsrBasicVsrAlgorithm()

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 320, height: 180 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: algorithm,
    })

    expect(model.superResolutionMetricRows[0]?.value).toBe('6.33M')
    expect(model.isSuperResolutionScaleLocked).toBe(false)
    expect(model.superResolutionModelLicense?.usage).toBe('non_commercial')
    expect(model.superResolutionModelLabel).toBe('Real-RawVSR BasicVSR')
  })

  it('uses selected TensorRT engine metrics for super-resolution estimates', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'tensorrt'
    workflow.superResolution.algorithm = 'ppmsvsr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 5

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.superResolutionMetricRows[1].value).toBe('22.1 GFLOPs')
    expect(model.superResolutionMetricRows[2].value).toBe('3.17 GiB')
  })

  it('does not expose a combined peak when either stage is disabled', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.superResolution.enabled = false

    const model = buildEnhanceReadModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.combinedVramMetricRows).toEqual([])
  })
})
